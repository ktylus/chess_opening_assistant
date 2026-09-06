import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.app import create_app


class FakeClient:
    async def stream(self, chat_request):
        yield "test response"


class FakeCache:
    def __init__(self):
        self.closed = False

    def get(self, key, *, tool):
        return None

    def set(self, key, value, *, tool, ttl_seconds):
        pass

    def close(self):
        self.closed = True


def test_lifespan_creates_one_shared_client():
    created = []
    cache = FakeCache()

    def client_factory(received_cache):
        assert received_cache is cache
        client = FakeClient()
        created.append(client)
        return client

    app = create_app(client_factory, lambda: cache)  # type: ignore[arg-type]

    with TestClient(app) as test_client:
        assert app.state.client is created[0]
        assert test_client.get("/health").json() == {"status": "ok"}
        response = test_client.post("/chat", json={"messages": [], "pgn": ""})

    assert response.text == "test response"
    assert len(created) == 1
    assert cache.closed


@pytest.mark.parametrize("fails", [False, True])
def test_submissions_count_before_response_even_when_rate_limited(caplog, fails):
    class ClientWithOutcome:
        async def stream(self, chat_request):
            if fails:
                raise RuntimeError("assistant unavailable")
            yield "response"

    app = create_app(lambda cache: ClientWithOutcome(), FakeCache)
    browser_id = str(uuid4())
    headers = {"X-Browser-ID": browser_id}
    with (
        TestClient(app, raise_server_exceptions=False) as client,
        caplog.at_level(logging.INFO, logger="chess_opening_assistant.http"),
    ):
        client.get("/health", headers=headers)
        # Enough requests to hit the production limiter.
        responses = [
            client.post(
                "/chat",
                headers=headers,
                json={"messages": [{"role": "user", "content": "private question"}]},
            )
            for _ in range(11)
        ]
    assert responses[-1].status_code == 429
    records = [r for r in caplog.records if r.msg == "question_submitted"]
    assert len(records) == 11
    assert all(r.event == {"browser_id": browser_id} for r in records)


@pytest.mark.parametrize("browser_id", [None, "arbitrary identifying text"])
def test_missing_or_invalid_browser_id_does_not_break_chat(caplog, browser_id):
    app = create_app(lambda cache: FakeClient(), FakeCache)
    headers = {"X-Browser-ID": browser_id} if browser_id else {}
    with (
        TestClient(app) as client,
        caplog.at_level(logging.INFO, logger="chess_opening_assistant.http"),
    ):
        response = client.post("/chat", headers=headers, json={"messages": []})
    assert response.text == "test response"
    record = next(r for r in caplog.records if r.msg == "question_submitted")
    assert record.event == {"browser_id": None}
