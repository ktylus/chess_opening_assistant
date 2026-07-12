import json
import logging
import sys

from backend.observability import ChatEvent, Outcome, bind_conversation, bind_request
from backend.observability.logging_config import JsonFormatter, RequestContextFilter


def render(record: logging.LogRecord) -> dict:
    """Push a record through the filter and formatter, as a handler would."""
    RequestContextFilter().filter(record)
    return json.loads(JsonFormatter().format(record))


def make_record(message="hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=message,
        args=None,
        exc_info=None,
    )
    record.__dict__.update(extra)
    return record


def test_records_carry_the_current_request_and_conversation():
    bind_request("req-1")
    bind_conversation("conv-1")

    payload = render(make_record())

    assert payload["request_id"] == "req-1"
    assert payload["conversation_id"] == "conv-1"
    assert payload["message"] == "hello"


def test_event_fields_are_merged_into_the_top_level():
    bind_request("req-2")
    event = ChatEvent(docs_hit=True, docs_count=2, outcome=Outcome.COMPLETED)

    payload = render(make_record("chat_completed", event=event.__dict__))

    assert payload["docs_hit"] is True
    assert payload["docs_count"] == 2
    assert payload["outcome"] == "completed"


def test_unset_fields_are_omitted_rather_than_logged_as_null():
    bind_request("req-3")
    bind_conversation(None)

    payload = render(make_record("chat_completed", event={"ttft_ms": None}))

    assert "conversation_id" not in payload
    assert "ttft_ms" not in payload


def test_exceptions_are_rendered_into_the_line():
    bind_request("req-4")
    try:
        raise ValueError("Invalid PGN string")
    except ValueError:
        record = make_record("chat_failed")
        record.exc_info = sys.exc_info()

    payload = render(record)

    assert "Invalid PGN string" in payload["exception"]
    assert payload["request_id"] == "req-4"
