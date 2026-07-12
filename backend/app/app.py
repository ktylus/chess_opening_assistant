from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from backend.agent.chat_models import ChatRequest
from backend.agent.client import Client
from backend.app.middleware import RequestContextMiddleware
from backend.observability import bind_conversation, configure_logging

configure_logging()

app = FastAPI()
app.add_middleware(RequestContextMiddleware)
client = Client()


@app.post("/chat")
async def chat(chat_request: ChatRequest):
    bind_conversation(chat_request.conversation_id)
    return StreamingResponse(client.stream(chat_request), media_type="text/plain")
