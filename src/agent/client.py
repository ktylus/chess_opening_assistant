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
from src.agent.tools import (
    make_lichess_masters_opening_explorer_tool,
    make_stockfish_eval_tool,
    retrieve_opening_docs,
)
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
        fen = pgn_to_fen(chat_request.pgn)
        agent_tools = [
            make_stockfish_eval_tool(fen),
            make_lichess_masters_opening_explorer_tool(fen),
        ]
        status_messages = {at.tool.name: at.status_message for at in agent_tools}
        agent = create_agent(self.model, tools=[at.tool for at in agent_tools])
        position_context = (
            f"\n\nCurrent position (PGN): {chat_request.pgn}"
            if chat_request.pgn
            else ""
        )
        system_message = SystemMessage(system_prompt + position_context)
        conversation = self._inject_retrieved_docs(
            self._to_langchain_messages(chat_request), fen
        )
        messages = {"messages": [system_message] + conversation}
        async for chunk in agent.astream(messages, stream_mode="messages"):  # type: ignore
            msg = chunk[0]  # type: ignore
            if isinstance(msg, AIMessageChunk):
                content = msg.content[0]["text"] if msg.content else ""  # type: ignore
            elif isinstance(msg, ToolMessage):
                content = (
                    status_messages.get(msg.name or "", "*Using tool...*") + "\n\n"
                )
            yield content  # type: ignore

    @staticmethod
    def _inject_retrieved_docs(
        messages: list[BaseMessage], fen: str
    ) -> list[BaseMessage]:
        """Place opening theory for the current position right before the latest
        user query, so it is adjacent to the question being answered.

        The docs are regenerated every turn and never persisted into history, so
        only the current position's docs are ever in context.
        """
        if not messages:
            return messages
        docs = retrieve_opening_docs(fen)
        if docs:
            content = (
                "Relevant opening theory for the position currently on the board:\n\n"
                f"{docs}\n\n"
                "Use it where helpful when answering the next question."
            )
        else:
            content = (
                "No opening theory was retrieved for the position currently on the "
                "board. Answer from your own knowledge and say so if the position is "
                "outside known opening theory."
            )
        return messages[:-1] + [HumanMessage(content), messages[-1]]

    @staticmethod
    def _to_langchain_messages(chat_request: ChatRequest) -> list[BaseMessage]:
        messages = []
        for message in chat_request.messages:
            if message.role == MessageRole.USER:
                messages.append(HumanMessage(message.content))
            elif message.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(message.content))
        return messages
