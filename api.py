from fastapi import FastAPI

from chat_models import ChatRequest
from llm import Client

app = FastAPI()


@app.post("/chat")
async def chat(chat_request: ChatRequest):
    client = Client()
    return client.invoke(chat_request)
