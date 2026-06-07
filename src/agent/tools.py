import json
import os
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine
from langchain.tools import tool
from langchain_core.tools import BaseTool

from src.agent.doc_models import OpeningDoc


@dataclass
class AgentTool:
    tool: BaseTool
    status_message: str


DEFAULT_DOCS_PATH = Path("data/wikibooks_openings/cleaned_openings.jsonl")
DEFAULT_STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")
STOCKFISH_THINK_TIME = 2.0
STOCKFISH_LINES = 3


def make_fen_retrieve_tool(fen: str, docs_path: Path = DEFAULT_DOCS_PATH):
    """
    Create a tool to retrieve documents with passed FEN and docs path.

    Args:
    - fen: str - FEN notation describing board position
    - docs_path: str - (optional) Path to the docs file
    Returns:
    - Tool to retrieve documents.
    """

    @tool
    def retrieve_docs_by_board_state() -> str:
        """Retrieve opening docs relating to the current board position."""
        docs = find_docs_by_fen(fen, docs_path)
        if not docs:
            return "No documents were found for this position."
        formatted = [
            f"[Document {i + 1}: {doc['metadata']['name']}]\n{doc['text']}"
            for i, doc in enumerate(docs)
        ]
        return "\n\n".join(formatted)

    return AgentTool(
        tool=retrieve_docs_by_board_state,
        status_message="*Searching opening theory...*",
    )


def make_stockfish_eval_tool(
    fen: str,
    stockfish_path: str = DEFAULT_STOCKFISH_PATH,
    think_time: float = STOCKFISH_THINK_TIME,
    num_lines: int = STOCKFISH_LINES,
):
    @tool
    def evaluate_position_with_stockfish() -> str:
        """Evaluate the current board position using Stockfish, returning the top engine lines with scores."""
        board = chess.Board(fen)
        with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
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


def find_docs_by_fen(fen: str, docs_path: Path = DEFAULT_DOCS_PATH) -> list[OpeningDoc]:
    with open(docs_path, encoding="utf-8") as f:
        doc_jsons = [line for line in f.read().split("\n") if line.strip()]
    doc_jsons = [json.loads(json_str) for json_str in doc_jsons]
    return [doc for doc in doc_jsons if doc["metadata"]["fen"] == fen]
