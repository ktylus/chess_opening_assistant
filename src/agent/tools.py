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

from src.agent.doc_models import OpeningDoc
from src.agent.prompts import DOC_FORMAT
from src.chess_utils.board_state import get_position_key_from_fen


@dataclass
class AgentTool:
    tool: BaseTool
    status_message: str


DEFAULT_DOCS_PATH = Path("data/wikibooks_openings/cleaned_openings.jsonl")
STOCKFISH_THINK_TIME = 2.0
STOCKFISH_LINES = 2
LICHESS_MASTERS_URL = "https://explorer.lichess.org/masters"
LICHESS_TOP_MOVES = 5


def retrieve_opening_docs(fen: str, docs_path: Path = DEFAULT_DOCS_PATH) -> str:
    """
    Retrieve and format opening docs for the given board position.

    Unlike the engine/explorer tools, this is not an agent tool: retrieval is
    driven by the position rather than chosen by the model, so the caller injects
    the result into context for every position. Returns an empty string when no
    documents match the position.
    """
    docs = _find_docs_for_position(fen, docs_path)
    if not docs:
        return ""
    formatted = [
        DOC_FORMAT.format(
            n=i + 1, name=doc["metadata"].get("name", ""), text=doc["text"]
        )
        for i, doc in enumerate(docs)
    ]
    return "\n\n".join(formatted)


def _find_docs_for_position(
    fen: str, docs_path: Path = DEFAULT_DOCS_PATH
) -> list[OpeningDoc]:
    key = get_position_key_from_fen(fen)
    with open(docs_path, encoding="utf-8") as f:
        doc_jsons = [line for line in f.read().split("\n") if line.strip()]
    doc_jsons = [json.loads(json_str) for json_str in doc_jsons]
    return [doc for doc in doc_jsons if doc["metadata"]["epd"] == key]


def make_stockfish_eval_tool(
    fen: str,
    stockfish_path: str | None = None,
    think_time: float = STOCKFISH_THINK_TIME,
    num_lines: int = STOCKFISH_LINES,
):
    resolved_path = stockfish_path or os.environ.get("STOCKFISH_PATH", "stockfish")

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
                score_str = "N/A"
            else:
                relative = score.white()
                if relative.is_mate():
                    score_str = f"M{relative.mate()}"
                else:
                    cp = relative.score(mate_score=10000)
                    score_str = f"{cp / 100:+.2f}"

            pv = info.get("pv", [])
            moves = " ".join(_moves_to_san(board.copy(), pv))
            lines.append(f"Line {i + 1} ({score_str}): {moves}")

        return "\n".join(lines)

    return AgentTool(
        tool=evaluate_position_with_stockfish,
        status_message="*Consulting Stockfish...*",
    )


def _moves_to_san(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    result = []
    for move in moves:
        if move not in board.legal_moves:
            break
        result.append(board.san(move))
        board.push(move)
    return result


def make_lichess_masters_opening_explorer_tool(fen: str):
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
            return "No master games found for this position."

        lines = [f"Total master games in this position: {position_total}\n"]
        lines.append("Most common continuations:")

        board = chess.Board(fen)
        for i, move in enumerate(data["moves"], start=1):
            move_total = move["white"] + move["draws"] + move["black"]
            if move_total == 0:
                continue
            san = board.san(chess.Move.from_uci(move["uci"]))
            prevalence = move_total / position_total * 100
            white_pct = move["white"] / move_total * 100
            draw_pct = move["draws"] / move_total * 100
            black_pct = move["black"] / move_total * 100
            lines.append(
                f"{i}. {san} — {prevalence:.0f}% of games"
                f" | White {white_pct:.0f}% / Draw {draw_pct:.0f}% / Black {black_pct:.0f}%"
            )

        return "\n".join(lines)

    return AgentTool(
        tool=get_lichess_masters_opening_data,
        status_message="*Consulting Lichess opening explorer (master games)...*",
    )
