import asyncio

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from backend.agent.chat_models import ChatRequest, Message, MessageRole
from backend.agent.client import ERROR_MESSAGE, Client, PreparedRun
from backend.observability import Outcome, start_event

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
RUY_LOPEZ_PGN = "1. e4 e5 2. Nf3 Nc6 3. Bb5"


class FakeAgent:
    """Stands in for the LangChain agent, replaying canned chunks."""

    def __init__(self, chunks, error=None):
        self.chunks = chunks
        self.error = error

    async def astream(self, messages, config=None, stream_mode=None):
        for chunk in self.chunks:
            yield (chunk, {})
        if self.error:
            raise self.error


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.client.init_chat_model", lambda **kwargs: object()
    )
    return Client()


def prepare_with(client, monkeypatch, agent):
    """Make the client run ``agent`` instead of a real one."""
    prepared = PreparedRun(
        agent=agent,
        messages={"messages": []},
        config={},
        status_messages={"stockfish": "*Consulting Stockfish...*"},
        retrieved_docs="",
    )
    monkeypatch.setattr(client, "_prepare", lambda chat_request: prepared)


async def collect(stream):
    return "".join([chunk async for chunk in stream])


async def test_completed_stream_records_tools_timing_and_outcome(client, monkeypatch):
    event = start_event()
    prepare_with(
        client,
        monkeypatch,
        FakeAgent(
            [
                AIMessageChunk(content="The Ruy "),
                ToolMessage(content="+0.30", tool_call_id="1", name="stockfish"),
                AIMessageChunk(content="Lopez."),
            ]
        ),
    )

    text = await collect(client.stream(ChatRequest(messages=[])))

    assert "The Ruy " in text
    assert "*Consulting Stockfish...*" in text
    assert event.outcome == Outcome.COMPLETED
    assert event.tools_called == ["stockfish"]
    assert event.chars_streamed == len(text)
    assert event.ttft_ms is not None
    assert event.total_ms is not None


async def test_failure_tells_the_user_and_records_error_outcome(client, monkeypatch):
    event = start_event()
    prepare_with(
        client,
        monkeypatch,
        FakeAgent([AIMessageChunk(content="Partial")], error=RuntimeError("boom")),
    )

    text = await collect(client.stream(ChatRequest(messages=[])))

    # The status code is already committed, so the failure has to reach the user
    # through the stream itself.
    assert text == "Partial" + ERROR_MESSAGE
    assert event.outcome == Outcome.ERROR


async def test_client_disconnect_is_recorded_and_propagates(client, monkeypatch):
    event = start_event()
    prepare_with(
        client,
        monkeypatch,
        FakeAgent([AIMessageChunk(content="Partial")], error=asyncio.CancelledError()),
    )

    with pytest.raises(asyncio.CancelledError):
        await collect(client.stream(ChatRequest(messages=[])))

    assert event.outcome == Outcome.CLIENT_DISCONNECT
    assert event.chars_streamed == len("Partial")


def test_record_request_captures_question_position_and_retrieval():
    event = start_event()
    chat_request = ChatRequest(
        messages=[
            Message(role=MessageRole.USER, content="Why Bb5?"),
            Message(role=MessageRole.ASSISTANT, content="It pins the knight."),
            Message(role=MessageRole.USER, content="And the pawn breaks?"),
        ],
        pgn=RUY_LOPEZ_PGN,
    )

    Client._record_request(chat_request, STARTING_FEN, docs=[{"text": "..."}])

    assert event.turn == 3
    assert event.question == "And the pawn breaks?"  # the latest one, not the first
    assert event.pgn == RUY_LOPEZ_PGN
    assert event.fen == STARTING_FEN
    assert event.ply == 0
    assert event.docs_hit is True
    assert event.docs_count == 1


def test_record_request_marks_a_retrieval_miss():
    event = start_event()

    Client._record_request(ChatRequest(messages=[]), STARTING_FEN, docs=[])

    assert event.docs_hit is False
    assert event.docs_count == 0
    assert event.question is None
