from pathlib import Path

import pytest

from backend.agent.tools import (
    STOCKFISH_LINES,
    _find_docs_for_position,
    make_lichess_masters_opening_explorer_tool,
    make_stockfish_eval_tool,
)
from backend.chess_utils.board_state import get_position_key_from_fen

TEST_DATA_PATH = Path(__file__).parent / "test_data.jsonl"

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.mark.parametrize(
    "fen, expected_names",
    [
        ("rnbqkbnr/pppppppp/8/8/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 0 1", ["Ware Opening"]),
        # Same position, different move counters (transposition): must still match.
        ("rnbqkbnr/pppppppp/8/8/P7/8/1PPPPPPP/RNBQKBNR b KQkq - 7 9", ["Ware Opening"]),
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
    docs = _find_docs_for_position(fen, TEST_DATA_PATH)
    assert [doc["metadata"]["name"] for doc in docs] == expected_names
    assert all(doc["metadata"]["epd"] == get_position_key_from_fen(fen) for doc in docs)


@pytest.mark.integration
def test_lichess_masters_opening_explorer_returns_data():
    agent_tool = make_lichess_masters_opening_explorer_tool(STARTING_FEN)
    result = agent_tool.tool.invoke({})
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.integration
def test_stockfish_eval_returns_correct_n_lines():
    agent_tool = make_stockfish_eval_tool(STARTING_FEN)
    result = agent_tool.tool.invoke({})
    lines = [line for line in result.strip().split("\n") if line]
    assert len(lines) == STOCKFISH_LINES
    for i, line in enumerate(lines, start=1):
        assert line.startswith(f"Line {i}")
