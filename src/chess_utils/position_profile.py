# Position profiling: extracts structured opening features from a PGN move sequence.
# PGN is preferred over FEN — opening lines are naturally expressed as move sequences.
# These features are injected into the system prompt to enrich LLM context.

import io
from dataclasses import dataclass
from enum import Enum

import chess
import chess.pgn

# Maps each minor piece home square to the piece type that belongs there
_WHITE_HOME_PIECES = {
    chess.B1: chess.KNIGHT,
    chess.G1: chess.KNIGHT,
    chess.C1: chess.BISHOP,
    chess.F1: chess.BISHOP,
}
_BLACK_HOME_PIECES = {
    chess.B8: chess.KNIGHT,
    chess.G8: chess.KNIGHT,
    chess.C8: chess.BISHOP,
    chess.F8: chess.BISHOP,
}


class CastlingState(Enum):
    NOT_YET_BOTH = "not yet castled (both sides available)"
    NOT_YET_KINGSIDE = "not yet castled (kingside only)"
    NOT_YET_QUEENSIDE = "not yet castled (queenside only)"
    CASTLED_KINGSIDE = "castled kingside"
    CASTLED_QUEENSIDE = "castled queenside"
    RIGHTS_FORFEITED = "castling rights forfeited"


@dataclass
class CastlingStatus:
    white: CastlingState
    black: CastlingState


@dataclass
class PositionProfile:
    # Which of e4/d4/e5/d5 are occupied and by whom; value is chess.WHITE or chess.BLACK
    center_pawns: dict[str, chess.Color]  # e.g. {"e4": chess.WHITE, "d5": chess.BLACK}
    # Number of minor pieces no longer on their starting squares
    white_developed: int
    black_developed: int
    castling: CastlingStatus


def _center_pawn_config(board: chess.Board) -> dict[str, chess.Color]:
    result: dict[str, chess.Color] = {}
    square_names = {chess.E4: "e4", chess.D4: "d4", chess.E5: "e5", chess.D5: "d5"}
    for sq, name in square_names.items():
        piece = board.piece_at(sq)
        if piece and piece.piece_type == chess.PAWN:
            result[name] = piece.color
    return result


def _development_counts(board: chess.Board) -> tuple[int, int]:
    def _count(home_pieces: dict, color: chess.Color) -> int:
        return sum(
            1
            for sq, piece_type in home_pieces.items()
            if board.piece_at(sq) != chess.Piece(piece_type, color)
        )

    return _count(_WHITE_HOME_PIECES, chess.WHITE), _count(
        _BLACK_HOME_PIECES, chess.BLACK
    )


def _castling_status(board: chess.Board) -> CastlingStatus:
    def side_status(color: chess.Color) -> CastlingState:
        ks = board.has_kingside_castling_rights(color)
        qs = board.has_queenside_castling_rights(color)
        if ks and qs:
            return CastlingState.NOT_YET_BOTH
        if ks:
            return CastlingState.NOT_YET_KINGSIDE
        if qs:
            return CastlingState.NOT_YET_QUEENSIDE
        # Rights gone — either already castled or king/rook moved.
        # python-chess doesn't track whether castling actually happened,
        # so we check king position as a heuristic.
        king_sq = board.king(color)
        if color == chess.WHITE:
            if king_sq == chess.G1:
                return CastlingState.CASTLED_KINGSIDE
            if king_sq == chess.C1:
                return CastlingState.CASTLED_QUEENSIDE
        else:
            if king_sq == chess.G8:
                return CastlingState.CASTLED_KINGSIDE
            if king_sq == chess.C8:
                return CastlingState.CASTLED_QUEENSIDE
        return CastlingState.RIGHTS_FORFEITED

    return CastlingStatus(
        white=side_status(chess.WHITE), black=side_status(chess.BLACK)
    )


def build_profile(pgn: str) -> PositionProfile:
    # Mirror get_fen_from_pgn: an empty PGN is the starting position, not an error.
    if not pgn.strip():
        board = chess.Board()
    else:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None or not game.mainline_moves():
            raise ValueError("Invalid PGN string")
        board = game.end().board()
    white_dev, black_dev = _development_counts(board)
    return PositionProfile(
        center_pawns=_center_pawn_config(board),
        white_developed=white_dev,
        black_developed=black_dev,
        castling=_castling_status(board),
    )


def profile_to_text(profile: PositionProfile) -> str:
    lines = ["## Position Profile"]

    if profile.center_pawns:
        center_desc = ", ".join(
            f"{sq} ({'white' if color == chess.WHITE else 'black'})"
            for sq, color in sorted(profile.center_pawns.items())
        )
    else:
        center_desc = "no pawns in the center"
    lines.append(f"Center pawns: {center_desc}")

    lines.append(
        f"Development: White has {profile.white_developed}/4 minor pieces developed, "
        f"Black has {profile.black_developed}/4."
    )

    lines.append(
        f"Castling — White: {profile.castling.white.value}; Black: {profile.castling.black.value}"
    )

    return "\n".join(lines)
