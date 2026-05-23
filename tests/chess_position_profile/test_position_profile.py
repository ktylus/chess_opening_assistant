import chess
import pytest

from chess_position_profile.position_profile import (
    CastlingState,
    build_profile,
    profile_to_text,
)

RUY_LOPEZ_STANDARD_PGN = "1. e4 e5 2. Nf3 Nc6 3. Bb5"
CASTLED_PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. O-O"


@pytest.fixture
def ruy_lopez_profile():
    return build_profile(RUY_LOPEZ_STANDARD_PGN)


@pytest.fixture
def castled_profile():
    return build_profile(CASTLED_PGN)


def test_ruy_lopez_center(ruy_lopez_profile):
    assert ruy_lopez_profile.center_pawns["e4"] == chess.WHITE
    assert ruy_lopez_profile.center_pawns["e5"] == chess.BLACK


def test_ruy_lopez_development(ruy_lopez_profile):
    assert ruy_lopez_profile.white_developed == 2
    assert ruy_lopez_profile.black_developed == 1


def test_ruy_lopez_castling(ruy_lopez_profile):
    assert ruy_lopez_profile.castling.white == CastlingState.NOT_YET_BOTH
    assert ruy_lopez_profile.castling.black == CastlingState.NOT_YET_BOTH


def test_ruy_lopez_text_output(ruy_lopez_profile):
    text = profile_to_text(ruy_lopez_profile)
    assert text == (
        "## Position Profile\n"
        "Center pawns: e4 (white), e5 (black)\n"
        "Development: White has 2/4 minor pieces developed, Black has 1/4.\n"
        "Castling — White: not yet castled (both sides available); Black: not yet castled (both sides available)"
    )


def test_castled_center(castled_profile):
    assert castled_profile.center_pawns["e4"] == chess.WHITE
    assert castled_profile.center_pawns["e5"] == chess.BLACK


def test_castled_development(castled_profile):
    assert castled_profile.white_developed == 2
    assert castled_profile.black_developed == 2


def test_castled_castling(castled_profile):
    assert castled_profile.castling.white == CastlingState.CASTLED_KINGSIDE
    assert castled_profile.castling.black == CastlingState.NOT_YET_BOTH


def test_castled_text_output(castled_profile):
    text = profile_to_text(castled_profile)
    assert text == (
        "## Position Profile\n"
        "Center pawns: e4 (white), e5 (black)\n"
        "Development: White has 2/4 minor pieces developed, Black has 2/4.\n"
        "Castling — White: castled kingside; Black: not yet castled (both sides available)"
    )
