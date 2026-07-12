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

from backend.agent.chat_models import ChatRequest, MessageRole
from backend.agent.prompt_bundle import PromptBundle, build_bundle
from backend.agent.tools import (
    make_lichess_masters_opening_explorer_tool,
    make_stockfish_eval_tool,
    retrieve_opening_docs,
)
from backend.chess_utils.board_state import get_fen_from_pgn
from backend.chess_utils.position_profile import build_profile, profile_to_text

MODEL = "gemini-3.1-flash-lite"


@dataclass
class PreparedRun:
    """Everything needed to drive one agent turn.

    ``retrieved_docs`` is the position-driven opening theory injected for this
    turn, surfaced separately from the message list.
    """

    agent: object
    messages: dict
    config: dict
    status_messages: dict[str, str]
    retrieved_docs: str


@dataclass
class AgentResponse:
    """Structured result of a non-streaming agent run."""

    text: str
    tool_calls: list[str] = field(default_factory=list)  # model-chosen tools fired
    contexts: list[str] = field(default_factory=list)  # grounding the answer used


class Client:
    def __init__(self):
        load_dotenv()
        self.model = init_chat_model(model=MODEL, model_provider="google_genai")

    @staticmethod
    def _make_agent_tools(fen: str) -> list:
        """Build the agent's tool set for a position."""
        return [
            make_stockfish_eval_tool(fen),
            make_lichess_masters_opening_explorer_tool(fen),
        ]

    def prompt_bundle(self) -> PromptBundle:
        """Return the active prompt bundle (prompt text + tool descriptions)."""
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
        config = {"metadata": {"prompt_version": bundle.version, "model": MODEL}}
        return PreparedRun(
            agent=agent,
            messages=messages,
            config=config,
            status_messages=status_messages,
            retrieved_docs=retrieved_docs,
        )

    async def run(self, chat_request: ChatRequest) -> AgentResponse:
        """Run the agent to completion, returning the answer text, the tools it
        called, and the contexts that grounded the answer."""
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
        """Run the agent and yield the response as text chunks, interleaving a
        status message whenever a tool is used."""
        prepared = self._prepare(chat_request)
        agent = prepared.agent
        messages = prepared.messages
        config = prepared.config
        status_messages = prepared.status_messages
        async for chunk in agent.astream(  # type: ignore
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
        """Insert current-position context (a position profile, then any
        retrieved opening theory) just before the latest user message.

        Returns the augmented message list and the retrieved opening docs (empty
        string if none).
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
