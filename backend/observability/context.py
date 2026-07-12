"""Request-scoped state for logging.

Holds the identifiers and the in-progress :class:`ChatEvent` for whatever
request is currently being served, so code deep in the agent can record what it
did without having a log record threaded through its signature.
"""

from contextvars import ContextVar
from uuid import uuid4

from backend.observability.events import ChatEvent

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_conversation_id: ContextVar[str | None] = ContextVar("conversation_id", default=None)
_chat_event: ContextVar[ChatEvent | None] = ContextVar("chat_event", default=None)


def new_request_id() -> str:
    """Return a fresh request identifier."""
    return uuid4().hex[:12]


def bind_request(request_id: str) -> None:
    """Make ``request_id`` the identifier for the current request."""
    _request_id.set(request_id)


def bind_conversation(conversation_id: str | None) -> None:
    """Make ``conversation_id`` the identifier for the current conversation."""
    _conversation_id.set(conversation_id)


def get_request_id() -> str | None:
    """Return the current request's identifier, if one is bound."""
    return _request_id.get()


def get_conversation_id() -> str | None:
    """Return the current conversation's identifier, if one is bound."""
    return _conversation_id.get()


def current_event() -> ChatEvent:
    """Return the event being accumulated for the current request.

    Creates and binds one if the caller is running outside a request (a direct
    library call, say), so callers never have to handle its absence.
    """
    event = _chat_event.get()
    if event is None:
        event = ChatEvent()
        _chat_event.set(event)
    return event


def start_event() -> ChatEvent:
    """Bind a fresh event to the current request and return it."""
    event = ChatEvent()
    _chat_event.set(event)
    return event
