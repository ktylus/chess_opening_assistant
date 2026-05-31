from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from chat_models import ChatRequest
from llm import Client

app = FastAPI()


@app.post("/chat")
async def chat(chat_request: ChatRequest):
    client = Client()
    return StreamingResponse(client.stream(chat_request), media_type="text/plain")
