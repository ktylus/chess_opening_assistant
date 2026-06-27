from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from src.agent.chat_models import ChatRequest, MessageRole
from src.agent.prompt_bundle import PromptBundle, build_bundle
from src.agent.tools import (
    make_lichess_masters_opening_explorer_tool,
    make_stockfish_eval_tool,
    retrieve_opening_docs,
)
from src.chess_utils.board_state import get_fen_from_pgn
from src.chess_utils.position_profile import build_profile, profile_to_text

MODEL = "gemini-3.5-flash"


@dataclass
class PreparedRun:
    """Everything needed to drive one agent turn, plus the context fed into it.

    ``retrieved_docs`` is the opening theory injected for this position (the
    deterministic, position-driven retrieval). It is surfaced here — rather than
    buried inside the message list — so callers like the eval harness can grade
    grounding against exactly what the model was given.
    """

    agent: object
    messages: dict
    config: dict
    status_messages: dict[str, str]
    retrieved_docs: str


@dataclass
class AgentResponse:
    """Structured result of a non-streaming agent run, for evaluation."""

    text: str
    tool_calls: list[str] = field(default_factory=list)  # model-chosen tools fired
    contexts: list[str] = field(default_factory=list)  # grounding the answer used


class Client:
    def __init__(self):
        load_dotenv()
        self.model = init_chat_model(model=MODEL, model_provider="google_genai")

    @staticmethod
    def _make_agent_tools(fen: str) -> list:
        """The agent's tool set for a position. Single source of truth, so the
        prompt bundle hashes exactly the tools the agent is actually given."""
        return [
            make_stockfish_eval_tool(fen),
            make_lichess_masters_opening_explorer_tool(fen),
        ]

    def prompt_bundle(self) -> PromptBundle:
        """The active prompt bundle (prompt text + live tool descriptions).

        Tool descriptions are static, so any position yields the same bundle; the
        eval harness uses ``.version`` to stamp runs with the prompt under test.
        """
        tools = [at.tool for at in self._make_agent_tools(get_fen_from_pgn(""))]
        return build_bundle(tools)

    def _prepare(self, chat_request: ChatRequest) -> PreparedRun:
        fen = get_fen_from_pgn(chat_request.pgn)
        agent_tools = self._make_agent_tools(fen)
        status_messages = {at.tool.name: at.status_message for at in agent_tools}
        tools = [at.tool for at in agent_tools]
        bundle = build_bundle(tools)
        agent = create_agent(self.model, tools=tools)
        position_context = (
            bundle.position_context_template.format(pgn=chat_request.pgn)
            if chat_request.pgn
            else ""
        )
        system_message = SystemMessage(bundle.system_prompt + position_context)
        conversation, retrieved_docs = self._inject_position_context(
            self._to_langchain_messages(chat_request), chat_request.pgn, fen, bundle
        )
        messages = {"messages": [system_message] + conversation}
        # Tag the run so the exact prompt bundle that produced it is queryable in
        # LangSmith (group/filter traces by prompt_version to attribute regressions).
        config = {"metadata": {"prompt_version": bundle.version, "model": MODEL}}
        return PreparedRun(
            agent=agent,
            messages=messages,
            config=config,
            status_messages=status_messages,
            retrieved_docs=retrieved_docs,
        )

    async def run(self, chat_request: ChatRequest) -> AgentResponse:
        """Run the agent to completion and return a structured result.

        Unlike ``stream``, this collects the full message list so we can report
        which tools the model chose and what context grounded its answer — the
        inputs the eval metrics need.
        """
        prepared = self._prepare(chat_request)
        result = await prepared.agent.ainvoke(prepared.messages, config=prepared.config)  # type: ignore
        out_messages = result["messages"]

        tool_calls = [
            call["name"]
            for msg in out_messages
            if isinstance(msg, AIMessage)
            for call in (msg.tool_calls or [])
        ]
        # Grounding = position-driven retrieval + whatever the tools returned.
        contexts: list[str] = []
        if prepared.retrieved_docs:
            contexts.append(prepared.retrieved_docs)
        contexts.extend(
            _message_text(msg.content)
            for msg in out_messages
            if isinstance(msg, ToolMessage)
        )
        text = next(
            (
                _message_text(msg.content)
                for msg in reversed(out_messages)
                if isinstance(msg, AIMessage) and _message_text(msg.content)
            ),
            "",
        )
        return AgentResponse(text=text, tool_calls=tool_calls, contexts=contexts)

    async def stream(self, chat_request: ChatRequest) -> AsyncGenerator[str]:
        prepared = self._prepare(chat_request)
        agent = prepared.agent
        messages = prepared.messages
        config = prepared.config
        status_messages = prepared.status_messages
        async for chunk in agent.astream( # type: ignore
            messages, config=config, stream_mode="messages"
        ):  # type: ignore
            msg = chunk[0]  # type: ignore
            if isinstance(msg, AIMessageChunk):
                text = _message_text(msg.content)
            elif isinstance(msg, ToolMessage):
                text = status_messages.get(msg.name or "", "*Using tool...*") + "\n\n"
            else:
                continue
            if text:
                yield text

    @staticmethod
    def _inject_position_context(
        messages: list[BaseMessage], pgn: str, fen: str, bundle: PromptBundle
    ) -> tuple[list[BaseMessage], str]:
        """Place context for the current position right before the latest user
        query, so it is adjacent to the question being answered: a structured
        position profile first, then retrieved opening theory.

        Both are regenerated every turn and never persisted into history, so only
        the current position's context is ever in scope. Returns the augmented
        message list together with the retrieved opening docs (empty string if
        none), so callers can grade grounding against what was injected.
        """
        if not messages:
            return messages, ""

        context = [
            HumanMessage(
                bundle.profile_preamble.format(
                    profile=profile_to_text(build_profile(pgn))
                )
            )
        ]

        docs = retrieve_opening_docs(fen)
        if docs:
            context.append(HumanMessage(bundle.docs_preamble.format(docs=docs)))
        else:
            context.append(HumanMessage(bundle.no_docs_fallback))

        return messages[:-1] + context + [messages[-1]], docs

    @staticmethod
    def _to_langchain_messages(chat_request: ChatRequest) -> list[BaseMessage]:
        messages = []
        for message in chat_request.messages:
            if message.role == MessageRole.USER:
                messages.append(HumanMessage(message.content))
            elif message.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(message.content))
        return messages


def _message_text(content: str | list) -> str:
    """Extract plain text from a message's content.

    Depending on the provider/version, content may be a plain string or a list
    of content blocks (strings and/or dicts like {"type": "text", "text": ...}).
    Both shapes are flattened to a string here; non-text blocks contribute "".
    """
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(block.get("text", ""))
    return "".join(parts)
