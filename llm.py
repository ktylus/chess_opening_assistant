import os

import anthropic
from anthropic import Anthropic
from dotenv import load_dotenv

BASE_SYSTEM_PROMPT = """
    You are a helpful assistant aiding in learning chess openings.
"""
MODEL = "claude-sonnet-4-6"

load_dotenv()

with open("data/wiki_articles/Sicilian_Defence.md") as f:
    doc = f.read()

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

history = []
while True:
    user_input = input("> ")
    history.append({"role": "user", "content": user_input})

    response = client.messages.create(
        max_tokens=2048,
        messages=history,
        model=MODEL,
        system=BASE_SYSTEM_PROMPT + "\n\n" + doc,
    )
    block = response.content[0]
    assert isinstance(block, anthropic.types.TextBlock)
    assistant_text = block.text
    history.append({"role": "assistant", "content": assistant_text})
    print(assistant_text)
