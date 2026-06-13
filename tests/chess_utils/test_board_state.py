import pytest

from src.chess_utils.board_state import get_fen_from_pgn

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_valid_pgn_returns_correct_fen():
    pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5"
    fen = get_fen_from_pgn(pgn)
    assert fen == "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"


def test_invalid_pgn_raises_value_error():
    with pytest.raises(ValueError, match="Invalid PGN string"):
        get_fen_from_pgn("not a pgn $$$$")


def test_empty_pgn_returns_starting_position():
    assert get_fen_from_pgn("") == STARTING_FEN
    assert get_fen_from_pgn("   ") == STARTING_FEN
