import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import InMemorySaver

from backend.agent.chat_models import ChatRequest, MessageRole
from backend.agent.prompt_bundle import PromptBundle, build_bundle
from backend.agent.tools import (
    Retrieval,
    make_lichess_masters_opening_explorer_tool,
    make_stockfish_eval_tool,
)
from backend.agent.workflow import WorkflowState, build_workflow, retrieval_from_state
from backend.cache import NoOpCache, ToolCache
from backend.chess_utils.position_profile import build_profile, profile_to_text
from backend.observability import (
    Outcome,
    current_event,
    get_conversation_id,
    get_request_id,
)
from backend.observability.provenance import git_sha

MODEL = "gemini-3.1-flash-lite"
MODEL_PROVIDER = "google_genai"
ERROR_MESSAGE = "\n\n*Something went wrong while answering that. Please try again.*"

logger = logging.getLogger("chess_opening_assistant.agent")


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
    # Kept for compatibility with tests and callers constructing PreparedRun;
    # graph runs now surface retrieved documents in their final state.
    retrieved_docs: str = ""


@dataclass
class AgentResponse:
    """Structured result of a non-streaming agent run."""

    text: str
    tool_calls: list[str] = field(default_factory=list)  # model-chosen tools fired
    contexts: list[str] = field(default_factory=list)  # grounding the answer used
    model_version: str | None = None  # the weights the provider says it served


class Client:
    def __init__(self, cache: ToolCache | None = None):
        load_dotenv()
        self.cache = cache or NoOpCache()
        self.model = init_chat_model(model=MODEL, model_provider=MODEL_PROVIDER)
        self.checkpointer = InMemorySaver()
        agent_tools = self._make_agent_tools(self.cache)
        self.status_messages = {
            agent_tool.tool.name: agent_tool.status_message
            for agent_tool in agent_tools
        }
        tools = [agent_tool.tool for agent_tool in agent_tools]
        self.bundle = build_bundle(tools)
        self.agent = build_workflow(
            self.model,
            self.bundle,
            tools,
            checkpointer=self.checkpointer,
            on_retrieval=lambda state: self._record_request(state, self.bundle),
        )

    @staticmethod
    def _make_agent_tools(cache: ToolCache | None = None) -> list:
        """Build tools whose position is supplied from workflow state."""
        return [
            make_stockfish_eval_tool(cache),
            make_lichess_masters_opening_explorer_tool(cache),
        ]

    def prompt_bundle(self) -> PromptBundle:
        """Return the active prompt bundle (prompt text + tool descriptions)."""
        return self.bundle

    def _prepare(self, chat_request: ChatRequest) -> PreparedRun:
        initial_state = {
            "input_messages": self._to_langchain_messages(chat_request),
            "agent_messages": [],
            "pgn": chat_request.pgn,
        }
        config = {
            "configurable": {
                "thread_id": chat_request.conversation_id or str(uuid.uuid4())
            },
            "metadata": {
                "prompt_version": self.bundle.version,
                "model": MODEL,
                "git_sha": git_sha(),
                "request_id": get_request_id(),
                "conversation_id": get_conversation_id(),
            }
        }
        return PreparedRun(
            agent=self.agent,
            messages=initial_state,
            config=config,
            status_messages=self.status_messages,
        )

    @staticmethod
    def _record_request(
        state: WorkflowState,
        bundle: PromptBundle,
    ) -> None:
        """Note what the incoming request asked about, and what is answering it,
        on the current event."""
        event = current_event()
        event.prompt_version = bundle.version
        event.model = MODEL
        event.git_sha = git_sha()
        input_messages = state["input_messages"]
        event.turn = len(input_messages)
        event.question = next(
            (
                message.content
                for message in reversed(input_messages)
                if isinstance(message, HumanMessage)
            ),
            None,
        )
        event.pgn = state["pgn"]
        event.fen = state["fen"]
        event.ply = state["ply"]
        retrieval = retrieval_from_state(state)
        event.docs_hit = bool(retrieval.docs)
        event.docs_count = len(retrieval.docs)
        event.docs_plies_back = retrieval.plies_back if retrieval.docs else None

    async def run(self, chat_request: ChatRequest) -> AgentResponse:
        """Run the agent to completion, returning the answer text, the tools it
        called, and the contexts that grounded the answer."""
        prepared = self._prepare(chat_request)
        result = await prepared.agent.ainvoke(prepared.messages, config=prepared.config)  # type: ignore
        out_messages = result["agent_messages"]

        tool_calls = [
            call["name"]
            for msg in out_messages
            if isinstance(msg, AIMessage)
            for call in (msg.tool_calls or [])
        ]
        # Grounding = position-driven retrieval + whatever the tools returned.
        contexts: list[str] = []
        formatted_docs = result.get("formatted_docs", "")
        if formatted_docs:
            contexts.append(formatted_docs)
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
        model_version = next(
            (
                version
                for msg in reversed(out_messages)
                if (version := _model_version(msg))
            ),
            None,
        )
        current_event().model_version = model_version
        return AgentResponse(
            text=text,
            tool_calls=tool_calls,
            contexts=contexts,
            model_version=model_version,
        )

    async def stream(self, chat_request: ChatRequest) -> AsyncGenerator[str]:
        """Run the agent and yield the response as text chunks, interleaving a
        status message whenever a tool is used."""
        event = current_event()
        started = time.perf_counter()
        try:
            prepared = self._prepare(chat_request)
            agent = prepared.agent
            messages = prepared.messages
            config = prepared.config
            status_messages = prepared.status_messages
            async for chunk in agent.astream(  # type: ignore
                messages, config=config, stream_mode="messages"
            ):  # type: ignore
                msg = chunk[0]  # type: ignore
                if isinstance(msg, (AIMessageChunk, AIMessage)):
                    text = _message_text(msg.content)
                    if text and event.ttft_ms is None:
                        event.ttft_ms = _elapsed_ms(started)
                    if event.model_version is None:
                        event.model_version = _model_version(msg)
                elif isinstance(msg, ToolMessage):
                    event.tools_called.append(msg.name or "unknown")
                    text = (
                        status_messages.get(msg.name or "", "*Using tool...*") + "\n\n"
                    )
                else:
                    continue
                if text:
                    event.chars_streamed += len(text)
                    yield text
            event.outcome = Outcome.COMPLETED
        except asyncio.CancelledError:
            # The client hung up mid-answer; record it, then let the cancellation
            # continue to propagate.
            event.outcome = Outcome.CLIENT_DISCONNECT
            raise
        except Exception:
            # The response has already begun, so the status code is committed and
            # the failure cannot surface as an HTTP error. Tell the user in the
            # stream itself rather than cutting them off mid-sentence.
            event.outcome = Outcome.ERROR
            logger.exception("chat_failed")
            yield ERROR_MESSAGE
        finally:
            event.total_ms = _elapsed_ms(started)
            event.emit()

    @staticmethod
    def _inject_position_context(
        messages: list[BaseMessage],
        pgn: str,
        retrieval: Retrieval,
        docs: str,
        bundle: PromptBundle,
    ) -> list[BaseMessage]:
        """Insert current-position context (a position profile, then any
        retrieved opening theory) just before the latest user message.

        Theory retrieved for an earlier position is labelled as such, so it is
        not read as a description of the position on the board.
        """
        if not messages:
            return messages

        context = [
            HumanMessage(
                bundle.profile_preamble.format(
                    profile=profile_to_text(build_profile(pgn))
                )
            )
        ]

        if docs and retrieval.is_exact:
            context.append(HumanMessage(bundle.docs_preamble.format(docs=docs)))
        elif docs:
            context.append(
                HumanMessage(
                    bundle.ancestor_docs_preamble.format(
                        docs=docs,
                        plies_back=retrieval.plies_back,
                        moves_since=" ".join(retrieval.moves_since),
                    )
                )
            )
        else:
            context.append(HumanMessage(bundle.no_docs_fallback))

        return messages[:-1] + context + [messages[-1]]

    @staticmethod
    def _to_langchain_messages(chat_request: ChatRequest) -> list[BaseMessage]:
        messages = []
        for message in chat_request.messages:
            if message.role == MessageRole.USER:
                messages.append(HumanMessage(message.content))
            elif message.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(message.content))
        return messages


def _elapsed_ms(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


def _model_version(message: BaseMessage) -> str | None:
    """Return the model the provider reports having served, if it says.

    ``MODEL`` is an alias the provider re-points at new weights over time, so it
    names a policy, not the thing that answered. This is the closest the API
    comes to naming the latter, and it is absent on most chunks of a stream.
    """
    metadata = getattr(message, "response_metadata", None) or {}
    return metadata.get("model_name") or metadata.get("model_version")


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
