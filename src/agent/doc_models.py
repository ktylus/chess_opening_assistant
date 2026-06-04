from typing import TypedDict


class DocMetadata(TypedDict):
    name: str
    pgn: str
    eco: str
    fen: str


class OpeningDoc(TypedDict):
    metadata: DocMetadata
    text: str
