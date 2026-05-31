from dotenv import load_dotenv
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.chat_models import ChatRequest, MessageRole

MODEL = "gemini-3.1-flash-lite"

load_dotenv()


model = ChatGoogleGenerativeAI(model=MODEL)

system_prompt = """
    You are a helpful assistant aiding in learning chess openings.
"""


class Client:
    def __init__(self):
        pass

    @staticmethod
    def _to_langchain_messages(chat_request: ChatRequest) -> list[BaseMessage]:
        messages = []
        for message in chat_request.messages:
            if message.role == MessageRole.USER:
                messages.append(HumanMessage(message.content))
            elif message.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(message.content))
        return messages

    async def stream(self, chat_request: ChatRequest):
        position_context = (
            f"\n\nCurrent position (PGN): {chat_request.pgn}"
            if chat_request.pgn
            else ""
        )
        system_message = SystemMessage(system_prompt + position_context)
        messages = [system_message] + self._to_langchain_messages(chat_request)
        async for chunk in model.astream(messages):
            content = chunk.content
            if isinstance(content, list):
                content = content[0] if content else ""
            if isinstance(content, dict):
                content = content.get("text", "")
            if content:
                yield content
