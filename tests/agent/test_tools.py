from pathlib import Path

import pytest

from src.agent.tools import _find_docs_by_fen, make_stockfish_eval_tool

TEST_DATA_PATH = Path(__file__).parent / "test_data.jsonl"

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.mark.parametrize(
    "fen, expected_names",
    [
        ("rnbqkbnr/pppppppp/8/8/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 0 1", ["Ware Opening"]),
        (
            "rnbqkbnr/pppppppp/8/8/8/1P6/P1PPPPPP/RNBQKBNR b KQkq - 0 1",
            ["Nimzowitsch–Larsen attack"],
        ),
        (
            "rnbqkbnr/pppp1ppp/8/4p3/8/1P6/P1PPPPPP/RNBQKBNR w KQkq - 0 2",
            ["Modern variation"],
        ),
        (
            "rnbqkbnr/pp1ppppp/8/2p5/1PP5/8/P2PPPPP/RNBQKBNR b KQkq - 0 2",
            ["Queen's Wing Gambit"],
        ),
        ("nonexistent fen", []),
    ],
)
def test_retrieve_docs_by_fen(fen, expected_names):
    docs = _find_docs_by_fen(fen, TEST_DATA_PATH)
    assert [doc["metadata"]["name"] for doc in docs] == expected_names
    assert all(doc["metadata"]["fen"] == fen for doc in docs)


def test_stockfish_eval_returns_three_lines():
    agent_tool = make_stockfish_eval_tool(STARTING_FEN)
    result = agent_tool.tool.invoke({})
    lines = [line for line in result.strip().split("\n") if line]
    assert len(lines) == 3
    for i, line in enumerate(lines, start=1):
        assert line.startswith(f"Line {i}")
