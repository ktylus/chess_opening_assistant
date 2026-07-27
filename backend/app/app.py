import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.agent.chat_models import ChatRequest
from backend.agent.client import Client
from backend.app.middleware import RequestContextMiddleware
from backend.app.rate_limit import RateLimitMiddleware
from backend.observability import bind_conversation, configure_logging

configure_logging()

app = FastAPI()
app.add_middleware(RequestContextMiddleware)
# Added last, so it wraps everything else and a refused request costs as little
# as possible. Only /chat is limited: /health is polled by the platform on a
# schedule, and a single page load pulls down many static assets.
app.add_middleware(RateLimitMiddleware, paths={"/chat"})
client = Client()


@app.get("/health")
async def health():
    """Liveness probe for the hosting platform. Touches no external service."""
    return {"status": "ok"}


@app.post("/chat")
async def chat(chat_request: ChatRequest):
    bind_conversation(chat_request.conversation_id)
    return StreamingResponse(client.stream(chat_request), media_type="text/plain")


# The production image bakes the built frontend in and serves it from here, so
# the browser only ever talks to one origin. In dev the Vite server owns the
# frontend and this directory is absent, so the mount is skipped.
#
# Mounted last on purpose: it matches every path, and routes resolve in order.
_frontend_dist = Path(os.getenv("FRONTEND_DIST", "frontend/dist"))
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
