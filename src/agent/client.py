from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from src.agent.chat_models import ChatRequest, MessageRole
from src.agent.tools import make_fen_retrieve_tool
from src.chess_utils.board_state import pgn_to_fen

MODEL = "gemini-3.1-flash-lite"

system_prompt = """
    You are a helpful assistant aiding in learning chess openings.
"""


class Client:
    def __init__(self):
        load_dotenv()
        self.model = init_chat_model(model=MODEL, model_provider="google_genai")

    async def stream(self, chat_request: ChatRequest) -> AsyncGenerator[str]:
        retrieval_tool = make_fen_retrieve_tool(pgn_to_fen(chat_request.pgn))
        agent = create_agent(self.model, tools=[retrieval_tool])
        position_context = (
            f"\n\nCurrent position (PGN): {chat_request.pgn}"
            if chat_request.pgn
            else ""
        )
        system_message = SystemMessage(system_prompt + position_context)
        messages = {
            "messages": [system_message] + self._to_langchain_messages(chat_request)
        }
        async for chunk in agent.astream(messages, stream_mode="messages"):  # type: ignore
            msg = chunk[0]  # type: ignore
            if isinstance(msg, AIMessageChunk):
                content = msg.content[0]["text"] if msg.content else ""  # type: ignore
            elif isinstance(msg, ToolMessage):
                content = msg.content
            yield content  # type: ignore

    @staticmethod
    def _to_langchain_messages(chat_request: ChatRequest) -> list[BaseMessage]:
        messages = []
        for message in chat_request.messages:
            if message.role == MessageRole.USER:
                messages.append(HumanMessage(message.content))
            elif message.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(message.content))
        return messages
