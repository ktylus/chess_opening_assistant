import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from backend.agent.chat_models import ChatRequest, Message, MessageRole
from backend.agent.client import AgentResponse, AnswerChunk, Client, PreparedRun
from backend.agent.workflow import WorkflowState


def make_client(monkeypatch, node):
    builder = StateGraph(WorkflowState)
    builder.add_node("answer", node)
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    client = object.__new__(Client)
    prepared = PreparedRun(builder.compile(), {"agent_messages": []}, {}, {})
    monkeypatch.setattr(client, "_prepare", lambda request: prepared)
    return client


def request():
    return ChatRequest(messages=[Message(role=MessageRole.USER, content="Explain")])


async def test_graph_stream_yields_fixed_answer_and_final_result(monkeypatch):
    def answer(state):
        return {"agent_messages": [AIMessage(content="Opening-only assistance.")]}

    client = make_client(monkeypatch, answer)
    events = [item async for item in client.stream_events(request())]
    assert [item.text for item in events if isinstance(item, AnswerChunk)] == [
        "Opening-only assistance."
    ]
    assert isinstance(events[-1], AgentResponse)
    assert events[-1].text == "Opening-only assistance."
    assert await client.run(request()) == events[-1]


async def test_run_propagates_graph_errors(monkeypatch):
    def fail(state):
        raise RuntimeError("graph failure")

    client = make_client(monkeypatch, fail)
    with pytest.raises(RuntimeError, match="graph failure"):
        await client.run(request())
