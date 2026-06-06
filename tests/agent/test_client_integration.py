import pytest

from src.agent.chat_models import ChatRequest, Message, MessageRole
from src.agent.client import Client


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def chat_request():
    return ChatRequest(messages=[Message(role=MessageRole.USER, content="test")])


@pytest.mark.asyncio
async def test_agent_responds(client, chat_request):
    chunks = []
    async for chunk in client.stream(chat_request):
        chunks.append(chunk)
    assert "".join(chunks)
