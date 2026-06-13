from src.data_preparation.clean_wikibooks import epd_from_moves

# Italian Game: 1. e4 e5 2. Nf3 Nc6 3. Bc4
# Both sides have all castling rights intact after 3 moves.
ITALIAN_GAME = "1. e4 e5 2. Nf3 Nc6 3. Bc4"
ITALIAN_GAME_EPD = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -"

# Ruy Lopez: white castles on move 5 (O-O), losing castling rights.
# Black still has both castling rights.
RUY_LOPEZ_OO = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O"
RUY_LOPEZ_OO_EPD = "r1bqkb1r/1ppp1ppp/p1n2n2/4p3/B3P3/5N2/PPPP1PPP/RNBQ1RK1 b kq -"

# Sicilian Najdorf: 1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6
# Both sides retain all castling rights.
SICILIAN_NAJDORF = "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6"
SICILIAN_NAJDORF_EPD = "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq -"

# Queen's Gambit Declined: 1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7
# Black's dark-squared bishop is developed to e7, clearing the way for O-O.
# Both sides still have all castling rights.
QGD = "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7"
QGD_EPD = "rnbqk2r/ppp1bppp/4pn2/3p2B1/2PP4/2N5/PP2PPPP/R2QKBNR w KQkq -"


def test_italian_game_epd():
    assert epd_from_moves(ITALIAN_GAME) == ITALIAN_GAME_EPD


def test_ruy_lopez_epd():
    assert epd_from_moves(RUY_LOPEZ_OO) == RUY_LOPEZ_OO_EPD


def test_sicilian_najdorf_epd():
    assert epd_from_moves(SICILIAN_NAJDORF) == SICILIAN_NAJDORF_EPD


def test_qgd_epd():
    assert epd_from_moves(QGD) == QGD_EPD


def test_empty_moves_returns_none():
    assert epd_from_moves("") is None
    assert epd_from_moves(None) is None


def test_invalid_moves_returns_none():
    assert epd_from_moves("1. e4 e5 2. Zz3") is None
