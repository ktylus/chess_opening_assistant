from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from backend.agent.prompt_bundle import build_bundle
from backend.agent.tools import Retrieval
from backend.agent.workflow import (
    DEEP_POSITION_REFUSAL,
    MAX_UNGROUNDED_OPENING_PLY,
    build_workflow,
    route_scope,
    should_refuse_position,
)
from tests.agent.factories import opening_doc


def test_scope_policy_allows_shallow_position_without_documents():
    assert not should_refuse_position(
        ply=MAX_UNGROUNDED_OPENING_PLY, has_exact_docs=False
    )


def test_scope_policy_refuses_deep_position_without_documents():
    assert should_refuse_position(
        ply=MAX_UNGROUNDED_OPENING_PLY + 1, has_exact_docs=False
    )


def test_scope_policy_allows_deep_position_with_exact_documents():
    assert not should_refuse_position(
        ply=MAX_UNGROUNDED_OPENING_PLY + 1, has_exact_docs=True
    )


def test_ancestor_documents_do_not_bypass_deep_position_gate():
    state = {
        "ply": MAX_UNGROUNDED_OPENING_PLY + 1,
        "retrieved_docs": [opening_doc()],
        "retrieval_is_exact": False,
    }

    assert route_scope(state) == "refuse"  # type: ignore[arg-type]


class ModelThatMustNotRun:
    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        raise AssertionError("the refusal branch must not call the model")


class ToolCallingModel:
    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": "lookup", "args": {}, "id": "call-1"}],
            )
        return AIMessage(content="Grounded answer")


class DuplicateToolCallingModel(ToolCallingModel):
    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "lookup", "args": {}, "id": "call-1"},
                    {"name": "lookup", "args": {}, "id": "call-2"},
                ],
            )
        return AIMessage(content="Used the evidence once")


async def test_refusal_branch_is_fixed_and_checkpointed(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.workflow.retrieve_opening_docs",
        lambda pgn: Retrieval(docs=[], plies_back=0, moves_since=()),
    )
    saver = InMemorySaver()
    graph = build_workflow(
        ModelThatMustNotRun(),  # type: ignore[arg-type]
        build_bundle([]),
        [],
        checkpointer=saver,
    )
    config = {"configurable": {"thread_id": "refusal-test"}}

    result = await graph.ainvoke(
        {
            "input_messages": [HumanMessage("What should I do?")],
            "agent_messages": [],
            "pgn": (
                "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 "
                "5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3"
            ),
        },
        config=config,
    )

    assert result["refusal_reason"] == "deep_position_without_exact_documents"
    assert result["agent_messages"] == [AIMessage(content=DEEP_POSITION_REFUSAL)]
    checkpoints = [snapshot async for snapshot in graph.aget_state_history(config)]
    assert len(checkpoints) >= 4


async def test_answer_branch_executes_tools_and_loops_back(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.workflow.retrieve_opening_docs",
        lambda pgn: Retrieval(docs=[], plies_back=0, moves_since=()),
    )

    @tool
    def lookup() -> str:
        """Return evidence for the current position."""
        return "evidence"

    model = ToolCallingModel()
    graph = build_workflow(
        model,  # type: ignore[arg-type]
        build_bundle([lookup]),
        [lookup],
    )

    result = await graph.ainvoke(
        {
            "input_messages": [HumanMessage("What is the plan?")],
            "agent_messages": [],
            "pgn": "1. e4",
        }
    )

    assert model.calls == 2
    assert [message.type for message in result["agent_messages"]] == [
        "ai",
        "tool",
        "ai",
    ]
    assert result["agent_messages"][-1].content == "Grounded answer"


async def test_duplicate_tool_requests_execute_only_once(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.workflow.retrieve_opening_docs",
        lambda pgn: Retrieval(docs=[], plies_back=0, moves_since=()),
    )
    executions = 0

    @tool
    def lookup() -> str:
        """Return evidence for the current position."""
        nonlocal executions
        executions += 1
        return "evidence"

    model = DuplicateToolCallingModel()
    graph = build_workflow(
        model,  # type: ignore[arg-type]
        build_bundle([lookup]),
        [lookup],
    )

    result = await graph.ainvoke(
        {
            "input_messages": [HumanMessage("What is the plan?")],
            "agent_messages": [],
            "pgn": "1. e4",
        }
    )

    assert executions == 1
    assert "already called in this response" in result["agent_messages"][-2].content


async def test_tool_can_be_called_again_in_a_later_model_response(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.workflow.retrieve_opening_docs",
        lambda pgn: Retrieval(docs=[], plies_back=0, moves_since=()),
    )
    executions = 0

    @tool
    def lookup() -> str:
        """Return evidence for the current position."""
        nonlocal executions
        executions += 1
        return f"evidence-{executions}"

    class RepeatingModel(ToolCallingModel):
        async def ainvoke(self, messages):
            self.calls += 1
            if self.calls <= 2:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "lookup",
                            "args": {},
                            "id": f"call-{self.calls}",
                        }
                    ],
                )
            return AIMessage(content="Used both results")

    model = RepeatingModel()
    graph = build_workflow(
        model,  # type: ignore[arg-type]
        build_bundle([lookup]),
        [lookup],
    )

    result = await graph.ainvoke(
        {
            "input_messages": [HumanMessage("Check that again.")],
            "agent_messages": [],
            "pgn": "1. e4",
        }
    )

    assert executions == 2
    assert result["agent_messages"][-1].content == "Used both results"
