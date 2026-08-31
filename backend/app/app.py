import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agent.chat_models import ChatRequest
from backend.agent.client import Client
from backend.app.middleware import RequestContextMiddleware
from backend.app.rate_limit import RateLimitMiddleware
from backend.cache import ToolCache, cache_from_env
from backend.observability import bind_conversation, configure_logging

configure_logging()


def create_app(
    client_factory: Callable[[ToolCache], Client] = Client,
    cache_factory: Callable[[], ToolCache] = cache_from_env,
) -> FastAPI:
    """Create the API and own its shared resources for one process lifespan."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cache = cache_factory()
        app.state.client = client_factory(cache)
        try:
            yield
        finally:
            cache.close()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)
    # Added last, so it wraps everything else and a refused request costs as
    # little as possible. Only /chat is limited: /health is polled by the
    # platform, and a single page load pulls down many static assets.
    app.add_middleware(RateLimitMiddleware, paths={"/chat"})

    @app.get("/health")
    async def health():
        """Liveness probe for the platform. Touches no external service."""
        return {"status": "ok"}

    @app.post("/chat")
    async def chat(chat_request: ChatRequest, request: Request):
        bind_conversation(chat_request.conversation_id)
        client: Client = request.app.state.client
        return StreamingResponse(client.stream(chat_request), media_type="text/plain")

    # The production image bakes the built frontend in and serves it from here,
    # so the browser only ever talks to one origin. In dev the Vite server owns
    # the frontend and this directory is absent, so the mount is skipped.
    # Mounted last because it matches every path and routes resolve in order.
    frontend_dist = Path(os.getenv("FRONTEND_DIST", "frontend/dist"))
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


app = create_app()
