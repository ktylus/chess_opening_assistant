from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from backend.agent.chat_models import ChatRequest
from backend.agent.client import Client

app = FastAPI()
client = Client()


@app.post("/chat")
async def chat(chat_request: ChatRequest):
    return StreamingResponse(client.stream(chat_request), media_type="text/plain")
