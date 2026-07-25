import functools
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlencode

import chess
import chess.engine
import requests
from langchain.tools import tool
from langchain_core.tools import BaseTool

from backend.agent.doc_models import OpeningDoc
from backend.agent.prompts import DOC_FORMAT
from backend.chess_utils.board_state import get_position_lineage
from backend.observability.provenance import UNKNOWN


@dataclass
class AgentTool:
    tool: BaseTool
    status_message: str


@dataclass(frozen=True)
class Retrieval:
    """Opening docs retrieved for a position, and where they came from.

    ``plies_back`` is 0 when the docs describe the position on the board, and
    otherwise how many half-moves earlier the position they describe is;
    ``moves_since`` are the SAN moves played from there to the board position.
    """

    docs: list[OpeningDoc]
    plies_back: int
    moves_since: tuple[str, ...]

    @property
    def is_exact(self) -> bool:
        """Whether the docs describe the position on the board."""
        return self.plies_back == 0


DEFAULT_DOCS_PATH = Path("data/wikibooks_openings/cleaned_openings.jsonl")
MAX_RETRIEVAL_PLIES_BACK = 4
STOCKFISH_THINK_TIME = 2.0
STOCKFISH_LINES = 2
LICHESS_MASTERS_URL = "https://explorer.lichess.org/masters"
LICHESS_TOP_MOVES = 5


ENGINE_LINE = "Line {n} ({score}): {moves}"
ENGINE_SCORE_UNAVAILABLE = "N/A"
ENGINE_MATE_SCORE = "M{moves}"
ENGINE_PAWN_SCORE = "{pawns:+.2f}"

EXPLORER_HEADER = (
    "Total master games in this position: {total}\n\nMost common continuations:"
)
EXPLORER_MOVE = (
    "{n}. {san} — {prevalence:.0f}% of games"
    " | White {white:.0f}% / Draw {draw:.0f}% / Black {black:.0f}%"
)
EXPLORER_NO_GAMES = "No master games found for this position."


def model_facing_text() -> dict[str, str]:
    """Return every author-written string this module puts in front of the model.

    Tool *descriptions* are not included: they are read off the live tool objects
    and snapshotted separately by ``PromptBundle``.
    """
    return {
        "engine_line": ENGINE_LINE,
        "engine_score_unavailable": ENGINE_SCORE_UNAVAILABLE,
        "engine_mate_score": ENGINE_MATE_SCORE,
        "engine_pawn_score": ENGINE_PAWN_SCORE,
        "explorer_header": EXPLORER_HEADER,
        "explorer_move": EXPLORER_MOVE,
        "explorer_no_games": EXPLORER_NO_GAMES,
        "doc_format": DOC_FORMAT,
    }


def resolve_stockfish_path(stockfish_path: str | None = None) -> str:
    """Return the path to the Stockfish binary the tools will run."""
    return stockfish_path or os.environ.get("STOCKFISH_PATH", "stockfish")


@functools.cache
def stockfish_version(stockfish_path: str | None = None) -> str:
    """Return the name the Stockfish binary reports for itself, e.g.
    ``"Stockfish 17"``, or ``"unknown"`` if it cannot be run.

    The engine is resolved from the environment rather than pinned in the
    repository, so no commit identifies it, and different builds evaluate the
    same opening position differently.
    """
    try:
        with chess.engine.SimpleEngine.popen_uci(
            resolve_stockfish_path(stockfish_path)
        ) as engine:
            return engine.id.get("name", UNKNOWN)
    except Exception:
        return UNKNOWN


@functools.cache
def docs_version(docs_path: Path = DEFAULT_DOCS_PATH) -> str:
    """Content hash of the opening-docs corpus, or ``"unknown"`` if unreadable.

    The corpus is a generated artifact and the sole source of retrieved theory,
    so it is versioned in its own right rather than by the commit that happens
    to contain it.
    """
    try:
        digest = hashlib.sha256(docs_path.read_bytes()).hexdigest()
    except OSError:
        return UNKNOWN
    return digest[:12]


def tool_config() -> dict:
    """Return the tool settings and versions that shape what the model reads.

    Recorded alongside a run because these are model inputs that no commit
    pins: ``stockfish_think_time`` is wall-clock, so the engine's answer varies
    between runs of identical code, and the Lichess masters database is live and
    changes underneath the assistant over time.
    """
    return {
        "stockfish_version": stockfish_version(),
        "stockfish_think_time": STOCKFISH_THINK_TIME,
        "stockfish_lines": STOCKFISH_LINES,
        "lichess_masters_url": LICHESS_MASTERS_URL,
        "lichess_top_moves": LICHESS_TOP_MOVES,
        "docs_version": docs_version(),
        "max_retrieval_plies_back": MAX_RETRIEVAL_PLIES_BACK,
    }


def _load_docs(docs_path: Path) -> list[OpeningDoc]:
    with open(docs_path, encoding="utf-8") as f:
        doc_jsons = [line for line in f.read().split("\n") if line.strip()]
    return [json.loads(json_str) for json_str in doc_jsons]


def retrieve_opening_docs(
    pgn: str,
    docs_path: Path = DEFAULT_DOCS_PATH,
    max_plies_back: int = MAX_RETRIEVAL_PLIES_BACK,
) -> Retrieval:
    """Return the opening docs for the position the PGN reaches.

    When that position has no docs, earlier positions in the same game are tried
    in turn, up to ``max_plies_back`` half-moves back, and the docs of the first
    one that has any are returned. The result records how far back they came
    from, so callers can tell the model the theory is not about the position on
    the board.
    """
    docs = _load_docs(docs_path)
    for position in get_position_lineage(pgn, max_plies_back):
        matches = [doc for doc in docs if doc["metadata"]["epd"] == position.key]
        if matches:
            return Retrieval(
                docs=matches,
                plies_back=position.plies_back,
                moves_since=position.moves_since,
            )
    return Retrieval(docs=[], plies_back=0, moves_since=())


def format_opening_docs(docs: list[OpeningDoc]) -> str:
    """Render opening docs for the prompt, or return an empty string when there
    are none."""
    return "\n\n".join(
        DOC_FORMAT.format(
            n=i + 1, name=doc["metadata"].get("name", ""), text=doc["text"]
        )
        for i, doc in enumerate(docs)
    )


def make_stockfish_eval_tool(
    fen: str,
    stockfish_path: str | None = None,
    think_time: float = STOCKFISH_THINK_TIME,
    num_lines: int = STOCKFISH_LINES,
):
    """Build a tool that evaluates the given position with Stockfish."""
    resolved_path = resolve_stockfish_path(stockfish_path)

    @tool
    def evaluate_position_with_stockfish() -> str:
        """Evaluate the current board position using Stockfish, returning the top engine lines with scores."""
        board = chess.Board(fen)
        with chess.engine.SimpleEngine.popen_uci(resolved_path) as engine:
            results = engine.analyse(
                board,
                chess.engine.Limit(time=think_time),
                multipv=num_lines,
            )

        lines = []
        for i, info in enumerate(results):
            score = info.get("score")
            if score is None:
                score_str = ENGINE_SCORE_UNAVAILABLE
            else:
                relative = score.white()
                if relative.is_mate():
                    score_str = ENGINE_MATE_SCORE.format(moves=relative.mate())
                else:
                    cp = relative.score(mate_score=10000)
                    score_str = ENGINE_PAWN_SCORE.format(pawns=cp / 100)

            pv = info.get("pv", [])
            moves = " ".join(_moves_to_san(board.copy(), pv))
            lines.append(ENGINE_LINE.format(n=i + 1, score=score_str, moves=moves))

        return "\n".join(lines)

    return AgentTool(
        tool=evaluate_position_with_stockfish,
        status_message="*Consulting Stockfish...*",
    )


def _moves_to_san(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    """Convert a move sequence to SAN, stopping at the first illegal move."""
    result = []
    for move in moves:
        if move not in board.legal_moves:
            break
        result.append(board.san(move))
        board.push(move)
    return result


def make_lichess_masters_opening_explorer_tool(fen: str):
    """Build a tool that returns Lichess master-game statistics for the position."""
    token = os.environ.get("LICHESS_API_KEY")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    @tool
    def get_lichess_masters_opening_data() -> str:
        """Get move statistics from master games in the current position."""
        query = urlencode(
            {"fen": fen, "moves": LICHESS_TOP_MOVES, "topGames": 0}, quote_via=quote
        )
        response = requests.get(
            f"{LICHESS_MASTERS_URL}?{query}",
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        position_total = data["white"] + data["draws"] + data["black"]
        if position_total == 0:
            return EXPLORER_NO_GAMES

        lines = [EXPLORER_HEADER.format(total=position_total)]

        board = chess.Board(fen)
        for i, move in enumerate(data["moves"], start=1):
            move_total = move["white"] + move["draws"] + move["black"]
            if move_total == 0:
                continue
            san = board.san(chess.Move.from_uci(move["uci"]))
            lines.append(
                EXPLORER_MOVE.format(
                    n=i,
                    san=san,
                    prevalence=move_total / position_total * 100,
                    white=move["white"] / move_total * 100,
                    draw=move["draws"] / move_total * 100,
                    black=move["black"] / move_total * 100,
                )
            )

        return "\n".join(lines)

    return AgentTool(
        tool=get_lichess_masters_opening_data,
        status_message="*Consulting Lichess opening explorer (master games)...*",
    )
