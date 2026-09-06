"""HTTP-level wiring for request logging."""

import logging
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.observability import bind_request, new_request_id, start_event

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger("chess_opening_assistant.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Give every request an identifier and an event to accumulate into.

    The server owns the identifier and echoes it back on the response. Inbound
    values are not trusted because this is a public endpoint and identifiers
    are written to logs and tracing metadata.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = new_request_id()
        bind_request(request_id)
        start_event()

        if request.method == "POST" and request.url.path == "/chat":
            # Analytics only: never use this client-controlled ID for trust or
            # rate limiting. Validate before persisting any header content.
            try:
                browser_id = str(UUID(request.headers.get("X-Browser-ID", "")))
            except ValueError:
                browser_id = None
            logger.info(
                "question_submitted",
                extra={"event": {"browser_id": browser_id}},
            )

        logger.debug(
            "request_started",
            extra={"event": {"method": request.method, "path": request.url.path}},
        )

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
