import pytest

from backend.chess_utils.board_state import (
    get_fen_from_pgn,
    get_position_key_from_fen,
    get_position_lineage,
)

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


RUY_LOPEZ_PGN = "1. e4 e5 2. Nf3 Nc6 3. Bb5"


def test_lineage_without_walkback_is_the_current_position_only():
    lineage = get_position_lineage(RUY_LOPEZ_PGN)
    assert len(lineage) == 1
    assert lineage[0].plies_back == 0
    assert lineage[0].moves_since == ()
    assert lineage[0].key == get_position_key_from_fen(get_fen_from_pgn(RUY_LOPEZ_PGN))


def test_lineage_walks_back_nearest_ancestor_first():
    lineage = get_position_lineage(RUY_LOPEZ_PGN, max_plies_back=3)
    assert [position.plies_back for position in lineage] == [0, 1, 2, 3]
    assert [position.moves_since for position in lineage] == [
        (),
        ("Bb5",),
        ("Nc6", "Bb5"),
        ("Nf3", "Nc6", "Bb5"),
    ]
    # Each ancestor's key is the position that PGN prefix actually reaches.
    assert lineage[2].key == get_position_key_from_fen(
        get_fen_from_pgn("1. e4 e5 2. Nf3")
    )


def test_lineage_stops_at_the_start_of_the_game():
    lineage = get_position_lineage("1. e4 e5", max_plies_back=10)
    assert [position.plies_back for position in lineage] == [0, 1, 2]
    assert lineage[-1].key == get_position_key_from_fen(STARTING_FEN)


def test_lineage_of_empty_pgn_is_the_starting_position():
    lineage = get_position_lineage("", max_plies_back=4)
    assert len(lineage) == 1
    assert lineage[0].key == get_position_key_from_fen(STARTING_FEN)


def test_lineage_of_invalid_pgn_raises_value_error():
    with pytest.raises(ValueError, match="Invalid PGN string"):
        get_position_lineage("not a pgn $$$$", max_plies_back=2)
