from pathlib import Path

import pytest

from backend.agent.tools import (
    STOCKFISH_LINES,
    make_lichess_masters_opening_explorer_tool,
    make_stockfish_eval_tool,
    retrieve_opening_docs,
)
from backend.chess_utils.board_state import (
    get_fen_from_pgn,
    get_position_key_from_fen,
)

TEST_DATA_PATH = Path(__file__).parent / "test_data.jsonl"

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.mark.parametrize(
    "pgn, expected_names",
    [
        ("1. a4", ["Ware Opening"]),
        ("1. b3", ["Nimzowitsch–Larsen attack"]),
        ("1. b3 e5", ["Modern variation"]),
        ("1. c4 c5 2. b4", ["Queen's Wing Gambit"]),
        # Reached by a different move order: matching is by position, not by line.
        ("1. b4 c5 2. c4", ["Queen's Wing Gambit"]),
    ],
)
def test_retrieve_docs_for_the_position_on_the_board(pgn, expected_names):
    retrieval = retrieve_opening_docs(pgn, TEST_DATA_PATH, max_plies_back=0)
    assert [doc["metadata"]["name"] for doc in retrieval.docs] == expected_names
    assert all(
        doc["metadata"]["epd"] == get_position_key_from_fen(get_fen_from_pgn(pgn))
        for doc in retrieval.docs
    )


def test_exact_match_is_preferred_over_walking_back():
    retrieval = retrieve_opening_docs(
        "1. b4 e5 2. Bb2 Bxb4", TEST_DATA_PATH, max_plies_back=4
    )
    assert [doc["metadata"]["name"] for doc in retrieval.docs] == [
        "Polish Opening, Main Line"
    ]
    assert retrieval.is_exact
    assert retrieval.plies_back == 0
    assert retrieval.moves_since == ()


def test_walks_back_to_nearest_ancestor_with_docs():
    # No doc covers 1. b4 e5 2. Bb2 or 1. b4 e5; the nearest one is 1. b4.
    retrieval = retrieve_opening_docs(
        "1. b4 e5 2. Bb2", TEST_DATA_PATH, max_plies_back=4
    )
    assert [doc["metadata"]["name"] for doc in retrieval.docs] == ["Polish Opening"]
    assert not retrieval.is_exact
    assert retrieval.plies_back == 2
    assert retrieval.moves_since == ("e5", "Bb2")


def test_walk_back_stops_at_the_first_hit():
    # Both 1. c4 e5 2. Nc3 Nc6 and 1. c4 have docs; only the nearer is returned.
    retrieval = retrieve_opening_docs(
        "1. c4 e5 2. Nc3 Nc6 3. g3", TEST_DATA_PATH, max_plies_back=4
    )
    assert [doc["metadata"]["name"] for doc in retrieval.docs] == ["English Opening"]
    assert retrieval.plies_back == 1
    assert retrieval.moves_since == ("g3",)


def test_walk_back_respects_the_ply_cap():
    # 1. b4 is 3 plies back, so a cap of 2 must not reach it.
    pgn = "1. b4 e5 2. Bb2 Nc6"
    assert retrieve_opening_docs(pgn, TEST_DATA_PATH, max_plies_back=2).docs == []
    within_cap = retrieve_opening_docs(pgn, TEST_DATA_PATH, max_plies_back=3)
    assert [doc["metadata"]["name"] for doc in within_cap.docs] == ["Polish Opening"]


def test_no_walk_back_when_disabled():
    retrieval = retrieve_opening_docs(
        "1. b4 e5 2. Bb2", TEST_DATA_PATH, max_plies_back=0
    )
    assert retrieval.docs == []
    assert retrieval.plies_back == 0


def test_miss_reports_no_docs_at_zero_plies_back():
    retrieval = retrieve_opening_docs(
        "1. h4 h5 2. Rh3", TEST_DATA_PATH, max_plies_back=4
    )
    assert retrieval.docs == []
    assert retrieval.is_exact
    assert retrieval.moves_since == ()


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
