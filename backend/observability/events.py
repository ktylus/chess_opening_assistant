"""The wide event emitted once per chat request."""

import logging
from dataclasses import asdict, dataclass, field
from enum import StrEnum

logger = logging.getLogger("chess_opening_assistant.chat")


class Outcome(StrEnum):
    COMPLETED = "completed"
    CLIENT_DISCONNECT = "client_disconnect"
    ERROR = "error"


@dataclass
class ChatEvent:
    """One request's worth of facts, filled in as the request progresses.

    Stages of a request record what they know here; the finished record is
    written as a single log line by :meth:`emit`.

    The provenance fields carry the same keys the eval experiments are stamped
    with, so a complaint about a live answer and the experiment that scored the
    same configuration can be joined on ``prompt_version`` and ``git_sha``.
    """

    # What produced the answer:
    prompt_version: str | None = None
    model: str | None = None
    model_version: str | None = None  # what the provider says it served
    git_sha: str | None = None
    # What was asked:
    turn: int | None = None
    question: str | None = None
    pgn: str | None = None
    fen: str | None = None
    ply: int | None = None
    docs_hit: bool | None = None
    docs_count: int | None = None
    tools_called: list[str] = field(default_factory=list)
    ttft_ms: int | None = None
    total_ms: int | None = None
    chars_streamed: int = 0
    outcome: Outcome | None = None

    def emit(self) -> None:
        """Write the accumulated event as a single log record."""
        logger.info("chat_completed", extra={"event": asdict(self)})
