"""HTTP-level wiring for request logging."""

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.observability import bind_request, new_request_id, start_event

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger("chess_opening_assistant.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Give every request an identifier and an event to accumulate into.

    The identifier is taken from the ``X-Request-ID`` header when a caller or
    proxy supplied one, and is echoed back on the response.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        bind_request(request_id)
        start_event()

        logger.debug(
            "request_started",
            extra={"event": {"method": request.method, "path": request.url.path}},
        )

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
