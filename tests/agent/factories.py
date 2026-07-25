"""Builders for the typed structures the agent modules pass around.

Tests that only care about how many docs were retrieved still need whole
``OpeningDoc``s: the shape is what the rest of the code is written against, so
tests should not stand in bare dicts for it.
"""

from backend.agent.doc_models import DocMetadata, OpeningDoc
from backend.chess_utils.board_state import get_fen_from_pgn, get_position_key_from_fen

DEFAULT_DOC_PGN = "1. b4"
DEFAULT_DOC_NAME = "Polish Opening"
DEFAULT_DOC_TEXT = "1. b4 grabs queenside space at the cost of a loose pawn."


def opening_doc(
    pgn: str = DEFAULT_DOC_PGN,
    name: str = DEFAULT_DOC_NAME,
    text: str = DEFAULT_DOC_TEXT,
) -> OpeningDoc:
    """An opening doc about the position the given PGN reaches."""
    return OpeningDoc(
        metadata=DocMetadata(
            name=name,
            pgn=pgn,
            epd=get_position_key_from_fen(get_fen_from_pgn(pgn)),
        ),
        text=text,
    )
