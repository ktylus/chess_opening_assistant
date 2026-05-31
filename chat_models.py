from enum import Enum

from pydantic import BaseModel


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    pgn: str = ""
