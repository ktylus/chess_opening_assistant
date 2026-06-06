import io

import chess.pgn


def pgn_to_fen(pgn: str) -> str:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ValueError("Invalid PGN string")
    board = game.end().board()
    return board.fen()
