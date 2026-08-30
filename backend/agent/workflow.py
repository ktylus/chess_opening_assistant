from collections.abc import Callable
from typing import Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from backend.agent.doc_models import OpeningDoc
from backend.agent.prompt_bundle import PromptBundle
from backend.agent.tools import Retrieval, format_opening_docs, retrieve_opening_docs
from backend.chess_utils.board_state import get_fen_from_pgn, get_ply_from_fen
from backend.chess_utils.position_profile import build_profile, profile_to_text

# Positions after eight full moves are outside the ungrounded opening scope.
# Exact theory for the board position is the only exception; ancestor theory
# explains how the game arose, but does not ground claims about the current board.
MAX_UNGROUNDED_OPENING_PLY = 16
DEEP_POSITION_REFUSAL = (
    "This position is beyond the opening depth I currently support, and I "
    "could not retrieve theory for the exact position. Try an earlier position "
    "or ask about the opening that led here."
)


class WorkflowState(TypedDict):
    """Serializable state persisted after each LangGraph super-step."""

    input_messages: list[BaseMessage]
    agent_messages: list[BaseMessage]
    pgn: str
    fen: str
    ply: int
    position_profile: str
    retrieved_docs: list[OpeningDoc]
    formatted_docs: str
    retrieval_plies_back: int
    retrieval_moves_since: tuple[str, ...]
    retrieval_is_exact: bool
    refusal_reason: str | None


def should_refuse_position(
    *,
    ply: int,
    has_exact_docs: bool,
    max_ungrounded_ply: int = MAX_UNGROUNDED_OPENING_PLY,
) -> bool:
    """Return the deterministic opening-scope decision."""
    return ply > max_ungrounded_ply and not has_exact_docs


def prepare_position(state: WorkflowState) -> dict:
    fen = get_fen_from_pgn(state["pgn"])
    return {
        "fen": fen,
        "ply": get_ply_from_fen(fen),
        "position_profile": profile_to_text(build_profile(state["pgn"])),
        # A fresh request starts a fresh agent loop even when its thread already
        # has checkpoints. Conversation history remains client-provided for now.
        "agent_messages": [],
        "refusal_reason": None,
    }


def retrieve_theory(state: WorkflowState) -> dict:
    retrieval = retrieve_opening_docs(state["pgn"])
    return {
        "retrieved_docs": retrieval.docs,
        "formatted_docs": format_opening_docs(retrieval.docs),
        "retrieval_plies_back": retrieval.plies_back,
        "retrieval_moves_since": retrieval.moves_since,
        "retrieval_is_exact": retrieval.is_exact,
    }


def route_scope(state: WorkflowState) -> Literal["refuse", "answer"]:
    has_exact_docs = bool(state["retrieved_docs"]) and state["retrieval_is_exact"]
    if should_refuse_position(ply=state["ply"], has_exact_docs=has_exact_docs):
        return "refuse"
    return "answer"


def refuse_position(state: WorkflowState) -> dict:
    return {
        "agent_messages": [AIMessage(content=DEEP_POSITION_REFUSAL)],
        "refusal_reason": "deep_position_without_exact_documents",
    }


def _position_context(state: WorkflowState, bundle: PromptBundle) -> list[BaseMessage]:
    context: list[BaseMessage] = [
        HumanMessage(bundle.profile_preamble.format(profile=state["position_profile"]))
    ]
    docs = state["formatted_docs"]
    if docs and state["retrieval_is_exact"]:
        context.append(HumanMessage(bundle.docs_preamble.format(docs=docs)))
    elif docs:
        context.append(
            HumanMessage(
                bundle.ancestor_docs_preamble.format(
                    docs=docs,
                    plies_back=state["retrieval_plies_back"],
                    moves_since=" ".join(state["retrieval_moves_since"]),
                )
            )
        )
    else:
        context.append(HumanMessage(bundle.no_docs_fallback))
    return context


def _model_input(state: WorkflowState, bundle: PromptBundle) -> list[BaseMessage]:
    input_messages = state["input_messages"]
    position_context = (
        bundle.position_context_template.format(pgn=state["pgn"])
        if state["pgn"]
        else ""
    )
    system = SystemMessage(bundle.system_prompt + position_context)
    if not input_messages:
        conversation: list[BaseMessage] = _position_context(state, bundle)
    else:
        conversation = (
            input_messages[:-1]
            + _position_context(state, bundle)
            + [input_messages[-1]]
        )
    return [system, *conversation, *state["agent_messages"]]


def build_workflow(
    model: BaseChatModel,
    bundle: PromptBundle,
    tools: list[BaseTool],
    checkpointer=None,
    on_retrieval: Callable[[WorkflowState], None] | None = None,
):
    """Build the explicit retrieval, scope, agent, and tool workflow."""
    tools_by_name = {tool.name: tool for tool in tools}
    model_with_tools = model.bind_tools(tools)

    async def answer(state: WorkflowState) -> dict:
        response = await model_with_tools.ainvoke(_model_input(state, bundle))
        return {"agent_messages": [*state["agent_messages"], response]}

    async def call_tools(state: WorkflowState) -> dict:
        last = state["agent_messages"][-1]
        if not isinstance(last, AIMessage):
            return {}
        results: list[BaseMessage] = list(state["agent_messages"])
        called_in_response: set[str] = set()
        for call in last.tool_calls:
            tool_name = call["name"]
            if tool_name in called_in_response:
                results.append(
                    ToolMessage(
                        content=(
                            "This tool was already called in this response. "
                            "Use its previous result."
                        ),
                        tool_call_id=call["id"],
                        name=tool_name,
                    )
                )
                continue
            tool = tools_by_name[tool_name]
            call_args = dict(call.get("args", {}))
            # Inject trusted graph state into arguments hidden from the model.
            # This keeps the compiled graph position-independent while ensuring
            # the model cannot choose or alter the board passed to a tool.
            input_fields = tool.get_input_schema().model_fields
            model_fields = tool.tool_call_schema.model_fields
            if "fen" in input_fields and "fen" not in model_fields:
                call_args["fen"] = state["fen"]
            output = await tool.ainvoke(call_args)
            called_in_response.add(tool_name)
            results.append(
                ToolMessage(
                    content=str(output),
                    tool_call_id=call["id"],
                    name=tool_name,
                )
            )
        return {"agent_messages": results}

    def route_agent(state: WorkflowState) -> Literal["tools", "finish"]:
        last = state["agent_messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "finish"

    def record_retrieval(state: WorkflowState) -> dict:
        if on_retrieval is not None:
            on_retrieval(state)
        return {}

    builder = StateGraph(WorkflowState)
    builder.add_node("prepare_position", prepare_position)
    builder.add_node("retrieve_theory", retrieve_theory)
    builder.add_node("record_retrieval", record_retrieval)
    builder.add_node("refuse", refuse_position)
    builder.add_node("answer", answer)
    builder.add_node("tools", call_tools)
    builder.add_edge(START, "prepare_position")
    builder.add_edge("prepare_position", "retrieve_theory")
    builder.add_edge("retrieve_theory", "record_retrieval")
    builder.add_conditional_edges("record_retrieval", route_scope)
    builder.add_edge("refuse", END)
    builder.add_conditional_edges(
        "answer",
        route_agent,
        {"tools": "tools", "finish": END},
    )
    builder.add_edge("tools", "answer")
    return builder.compile(checkpointer=checkpointer)


def retrieval_from_state(state: WorkflowState) -> Retrieval:
    return Retrieval(
        docs=state["retrieved_docs"],
        plies_back=state["retrieval_plies_back"],
        moves_since=state["retrieval_moves_since"],
    )
