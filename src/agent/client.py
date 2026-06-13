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
from src.chess_utils.board_state import get_fen_from_pgn
from src.chess_utils.position_profile import build_profile, profile_to_text

MODEL = "gemini-3.1-flash-lite"

system_prompt = """
    You are a helpful assistant aiding in learning chess openings.
"""


class Client:
    def __init__(self):
        load_dotenv()
        self.model = init_chat_model(model=MODEL, model_provider="google_genai")

    async def stream(self, chat_request: ChatRequest) -> AsyncGenerator[str]:
        fen = get_fen_from_pgn(chat_request.pgn)
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
        conversation = self._inject_position_context(
            self._to_langchain_messages(chat_request), chat_request.pgn, fen
        )
        messages = {"messages": [system_message] + conversation}
        async for chunk in agent.astream(messages, stream_mode="messages"):  # type: ignore
            msg = chunk[0]  # type: ignore
            if isinstance(msg, AIMessageChunk):
                text = _chunk_text(msg.content)
            elif isinstance(msg, ToolMessage):
                text = status_messages.get(msg.name or "", "*Using tool...*") + "\n\n"
            else:
                continue
            if text:
                yield text

    @staticmethod
    def _inject_position_context(
        messages: list[BaseMessage], pgn: str, fen: str
    ) -> list[BaseMessage]:
        """Place context for the current position right before the latest user
        query, so it is adjacent to the question being answered: a structured
        position profile first, then retrieved opening theory.

        Both are regenerated every turn and never persisted into history, so only
        the current position's context is ever in scope.
        """
        if not messages:
            return messages

        context = [
            HumanMessage(
                "Structured profile of the position currently on the board:\n\n"
                f"{profile_to_text(build_profile(pgn))}"
            )
        ]

        docs = retrieve_opening_docs(fen)
        if docs:
            context.append(
                HumanMessage(
                    "Relevant opening theory for the position currently on the board:\n\n"
                    f"{docs}\n\n"
                    "Use it where helpful when answering the next question."
                )
            )
        else:
            context.append(
                HumanMessage(
                    "No opening theory was retrieved for the position currently on the "
                    "board. Answer from your own knowledge and say so if the position is "
                    "outside known opening theory."
                )
            )

        return messages[:-1] + context + [messages[-1]]

    @staticmethod
    def _to_langchain_messages(chat_request: ChatRequest) -> list[BaseMessage]:
        messages = []
        for message in chat_request.messages:
            if message.role == MessageRole.USER:
                messages.append(HumanMessage(message.content))
            elif message.role == MessageRole.ASSISTANT:
                messages.append(AIMessage(message.content))
        return messages


def _chunk_text(content: str | list) -> str:
    """Extract plain text from an AIMessageChunk's content.

    Depending on the provider/version, content may be a plain string or a list
    of content blocks (strings and/or dicts like {"type": "text", "text": ...}).
    Both shapes are flattened to a string here; non-text blocks contribute "".
    """
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(block.get("text", ""))
    return "".join(parts)
