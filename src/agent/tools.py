import json
from dataclasses import dataclass
from pathlib import Path

from langchain.tools import tool
from langchain_core.tools import BaseTool

from src.agent.doc_models import OpeningDoc


@dataclass
class AgentTool:
    tool: BaseTool
    status_message: str

DEFAULT_DOCS_PATH = Path("data/wikibooks_openings/cleaned_openings.jsonl")


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


def find_docs_by_fen(fen: str, docs_path: Path = DEFAULT_DOCS_PATH) -> list[OpeningDoc]:
    with open(docs_path, encoding="utf-8") as f:
        doc_jsons = [line for line in f.read().split("\n") if line.strip()]
    doc_jsons = [json.loads(json_str) for json_str in doc_jsons]
    return [doc for doc in doc_jsons if doc["metadata"]["fen"] == fen]
