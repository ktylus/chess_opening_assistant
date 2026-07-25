import io
from dataclasses import dataclass

import chess.pgn


@dataclass(frozen=True)
class LineagePosition:
    """A position on the path leading to the one currently on the board.

    ``plies_back`` is 0 for the current position and counts half-moves backwards
    from it. ``moves_since`` holds the SAN moves played from this position to
    reach the current one, in order.
    """

    key: str
    plies_back: int
    moves_since: tuple[str, ...]


def get_fen_from_pgn(pgn: str) -> str:
    """Return the FEN of the position reached after the moves in the PGN.

    An empty PGN yields the starting position. Raises ValueError if the PGN is
    invalid.
    """
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
    "Position-identity key: the FEN without its move counters."
    return " ".join(fen.split()[:4])


def get_ply_from_fen(fen: str) -> int:
    """Return the number of half-moves played to reach the position."""
    return chess.Board(fen).ply()


def get_position_lineage(pgn: str, max_plies_back: int = 0) -> list[LineagePosition]:
    """Return the position the PGN reaches followed by its ancestors, nearest first.

    At most ``max_plies_back`` ancestors are returned, and fewer when the game is
    shorter than that. Raises ValueError if the PGN is invalid.
    """
    if not pgn.strip():
        board = chess.Board()
        return [LineagePosition(get_position_key_from_fen(board.fen()), 0, ())]

    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or not game.mainline_moves():
        raise ValueError("Invalid PGN string")

    board = game.board()
    keys = [get_position_key_from_fen(board.fen())]
    sans: list[str] = []
    for move in game.mainline_moves():
        sans.append(board.san(move))
        board.push(move)
        keys.append(get_position_key_from_fen(board.fen()))

    last = len(keys) - 1
    return [
        LineagePosition(
            key=keys[last - plies_back],
            plies_back=plies_back,
            moves_since=tuple(sans[last - plies_back :]),
        )
        for plies_back in range(min(max_plies_back, last) + 1)
    ]
