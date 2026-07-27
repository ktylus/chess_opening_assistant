from enum import Enum

from pydantic import BaseModel, Field

# Ceilings on what one request can ask the model to read. They exist to bound
# cost on a public endpoint, so they are set well above any legitimate use
# rather than tuned: the assistant answers questions about an opening position,
# and the scope is six moves deep.
MAX_MESSAGE_CHARS = 2_000
MAX_MESSAGES = 40
MAX_PGN_CHARS = 500


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: MessageRole
    content: str = Field(max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(max_length=MAX_MESSAGES)
    pgn: str = Field(default="", max_length=MAX_PGN_CHARS)
    conversation_id: str | None = None
