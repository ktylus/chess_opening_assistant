import os

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

MODEL = "gemini-3.1-flash-lite"

load_dotenv()


client = ChatGoogleGenerativeAI(model=MODEL)

with open("data/wiki_articles/Sicilian_Defence.md") as f:
    doc = f.read()
system_prompt = (
    """
    You are a helpful assistant aiding in learning chess openings.
"""
    + doc
)
messages: list[BaseMessage] = [SystemMessage(system_prompt)]
while True:
    user_input = input("> ")
    messages.append(HumanMessage(user_input))
    response = client.invoke(messages)
    messages.append(response)
    first = (
        response.content[0] if isinstance(response.content, list) else response.content
    )
    text = first if isinstance(first, str) else first["text"]
    print(text)
    break
