"""Logging setup: one JSON object per line on stdout.

Every record carries the current request and conversation identifiers, so an
error raised anywhere during a request can be tied back to the chat event that
describes it.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime

from backend.observability.context import get_conversation_id, get_request_id

# Attributes the stdlib puts on every record; anything else was added by us.
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class RequestContextFilter(logging.Filter):
    """Stamp the current request/conversation identifiers onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.conversation_id = get_conversation_id()
        return True


class JsonFormatter(logging.Formatter):
    """Render a record as a single-line JSON object.

    Fields passed via ``extra={"event": {...}}`` are merged into the top level.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "conversation_id": getattr(record, "conversation_id", None),
        }
        payload.update(getattr(record, "event", {}))
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in _RESERVED and key != "event"
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(
            {k: v for k, v in payload.items() if v is not None}, default=str
        )


def configure_logging() -> None:
    """Install the application's log handler.

    ``LOG_LEVEL`` sets the threshold (default ``INFO``); ``LOG_FORMAT=pretty``
    swaps the JSON output for a human-readable line during local development.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    pretty = os.environ.get("LOG_FORMAT", "json").lower() == "pretty"

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(
        logging.Formatter("%(levelname)s %(name)s [%(request_id)s] %(message)s")
        if pretty
        else JsonFormatter()
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Uvicorn installs its own handlers; drop them so its records flow through
    # ours and come out in the same format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
