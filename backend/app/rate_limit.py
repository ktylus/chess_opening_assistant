"""Per-IP request throttling for publicly reachable endpoints."""

import logging
import time
from collections import defaultdict, deque
from collections.abc import Iterable, Sequence

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("chess_opening_assistant.http")

# (requests, seconds), all enforced together. The short window stops a burst;
# the long one stops a patient caller from spending a day's model budget one
# well-spaced request at a time.
DEFAULT_LIMITS: tuple[tuple[int, int], ...] = ((10, 60), (200, 86_400))

# Clients whose history has fully expired are dropped every this many counted
# requests, so a stream of single-shot addresses cannot grow the table forever.
SWEEP_INTERVAL = 500


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Refuse requests from a client that has exceeded any configured limit.

    ``limits`` is a sequence of ``(requests, window_seconds)`` pairs, every one
    of which applies. Only requests whose path appears in ``paths`` are counted
    or refused; anything else passes straight through.

    Refused requests get a 429 and a ``Retry-After`` header.

    Counters live in the process and are lost on restart, which is only a
    correct implementation while the service runs as a single instance.
    """

    def __init__(
        self,
        app,
        *,
        paths: Iterable[str],
        limits: Sequence[tuple[int, int]] = DEFAULT_LIMITS,
    ):
        super().__init__(app)
        self._paths = frozenset(paths)
        self._limits = tuple(limits)
        self._horizon = max(window for _, window in self._limits)
        self._history: dict[str, deque[float]] = defaultdict(deque)
        self._counted_since_sweep = 0

    async def dispatch(self, request: Request, call_next):
        if request.url.path not in self._paths:
            return await call_next(request)

        # Behind the platform's proxy this is the forwarded client address
        # rather than the proxy's, because uvicorn is started with
        # --proxy-headers; see the CMD in backend/Dockerfile.
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()

        retry_after = self._retry_after(client, now)
        if retry_after is not None:
            logger.warning(
                "rate_limited",
                extra={
                    "event": {
                        "client": client,
                        "path": request.url.path,
                        "retry_after_s": retry_after,
                    }
                },
            )
            return JSONResponse(
                {"detail": "Too many requests. Please wait and try again."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        # Read and write happen with no await in between, so the event loop
        # cannot interleave another request here and no lock is needed.
        self._history[client].append(now)
        self._sweep_periodically(now)
        return await call_next(request)

    def _retry_after(self, client: str, now: float) -> int | None:
        """Seconds until ``client`` may retry, or ``None`` if it may proceed."""
        history = self._history[client]
        while history and history[0] <= now - self._horizon:
            history.popleft()

        wait = 0
        for allowed, window in self._limits:
            in_window = sum(1 for stamp in history if stamp > now - window)
            if in_window >= allowed:
                # The limit frees up when the oldest request still inside this
                # window falls out of it.
                expires_at = history[-allowed] + window
                wait = max(wait, int(expires_at - now) + 1)
        return wait or None

    def _sweep_periodically(self, now: float) -> None:
        self._counted_since_sweep += 1
        if self._counted_since_sweep < SWEEP_INTERVAL:
            return

        self._counted_since_sweep = 0
        cutoff = now - self._horizon
        stale = [
            client
            for client, history in self._history.items()
            if not history or history[-1] <= cutoff
        ]
        for client in stale:
            del self._history[client]
