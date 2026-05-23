from chess_position_profile.eco_codes import get_eco_code

# Owen Defense: Matovinsky Gambit
# B00 -- 1. e4 b6 2. d4 Bb7 3. Bd3 f5 4. exf5 Bxg2 5. Qh5+ g6
MATCH_BY_POPPING_PGN = (
    "1. e4 b6 2. d4 Bb7 3. Bd3 f5 4. exf5 Bxg2 5. Qh5+ g6 6. fxg6 Bg7"
)
# Sicilian Defense: Accelerated Dragon, Maróczy Bind, Gurgenidze Variation
# B36 -- 1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 g6 5. c4 Nf6 6. Nc3 Nxd4 7. Qxd4 d6
EXACT_MATCH_LONGEST_VARIATION_PGN = (
    "1. e4 c5 2. Nf3 Nc6 3. d4 cxd4 4. Nxd4 g6 5. c4 Nf6 6. Nc3 Nxd4 7. Qxd4 d6"
)
# Ruy Lopez: Morphy Defense, Steinitz Deferred
# C79 -- 1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O d6
EXACT_MATCH_NOT_LONGEST_PGN = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O d6"
# King's Pawn Game
# B00 -- 1. e4
ONE_PLY_PGN = "1. e4"


def test_match_by_popping():
    assert get_eco_code(MATCH_BY_POPPING_PGN) == "B00"


def test_exact_match_longest_variation():
    assert get_eco_code(EXACT_MATCH_LONGEST_VARIATION_PGN) == "B36"


def test_exact_match_not_longest():
    assert get_eco_code(EXACT_MATCH_NOT_LONGEST_PGN) == "C79"


def test_one_ply():
    assert get_eco_code(ONE_PLY_PGN) == "B00"
