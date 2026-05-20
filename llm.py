from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from chat_models import ChatRequest, MessageRole

MODEL = "gemini-3.1-flash-lite"

load_dotenv()


model = ChatGoogleGenerativeAI(model=MODEL)

with open("data/wiki_articles/Sicilian_Defence.md") as f:
    doc = f.read()
system_prompt = (
    """
    You are a helpful assistant aiding in learning chess openings.
"""
    + doc
)


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

    def invoke(self, chat_request: ChatRequest) -> str:
        system_message = SystemMessage(system_prompt)
        messages = [system_message] + self._to_langchain_messages(chat_request)
        response = model.invoke(messages)
        first = (
            response.content[0]
            if isinstance(response.content, list)
            else response.content
        )
        text = first if isinstance(first, str) else first["text"]
        return text
