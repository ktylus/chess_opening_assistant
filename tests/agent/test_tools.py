from pathlib import Path

import pytest

from src.agent.tools import find_docs_by_fen

TEST_DATA_PATH = Path(__file__).parent / "test_data.jsonl"


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
    docs = find_docs_by_fen(fen, TEST_DATA_PATH)
    assert [doc["metadata"]["name"] for doc in docs] == expected_names
    assert all(doc["metadata"]["fen"] == fen for doc in docs)
