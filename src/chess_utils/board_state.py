import io

import chess.pgn


def get_fen_from_pgn(pgn: str) -> str:
    if not pgn.strip():
        return chess.Board().fen()
    game = chess.pgn.read_game(io.StringIO(pgn))
    # python-chess PGN parser is lenient - parses incorrent PGNs
    # as empty valid chess games.
    if game is None or not game.mainline_moves():
        raise ValueError("Invalid PGN string")
    board = game.end().board()
    return board.fen()


def get_position_key_from_fen(fen: str) -> str:
    "Position-identity key: the FEN without its move counters (== board.epd())."
    return " ".join(fen.split()[:4])
