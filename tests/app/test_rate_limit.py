import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.agent.chat_models import MAX_MESSAGE_CHARS, MAX_MESSAGES, ChatRequest
from backend.app.rate_limit import RateLimitMiddleware


def make_app(limits=((3, 60),)):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, paths={"/limited"}, limits=limits)

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    @app.get("/open")
    async def unlimited():
        return {"ok": True}

    return app


@pytest.fixture
def client():
    return TestClient(make_app())


def test_requests_under_the_limit_are_served(client):
    for _ in range(3):
        assert client.get("/limited").status_code == 200


def test_request_over_the_limit_is_refused(client):
    for _ in range(3):
        client.get("/limited")

    response = client.get("/limited")

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_unlisted_paths_are_never_limited(client):
    for _ in range(10):
        assert client.get("/open").status_code == 200


def test_clients_are_counted_separately():
    app = make_app()
    noisy = TestClient(app, client=("10.0.0.1", 1000))
    quiet = TestClient(app, client=("10.0.0.2", 1000))

    for _ in range(4):
        noisy.get("/limited")

    assert noisy.get("/limited").status_code == 429
    assert quiet.get("/limited").status_code == 200


def test_every_configured_window_applies():
    # Generous short window, tight long one: the burst limit alone would let
    # all of these through.
    client = TestClient(make_app(limits=((100, 60), (2, 3_600))))

    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 429


def test_oversized_message_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[{"role": "user", "content": "x" * (MAX_MESSAGE_CHARS + 1)}]
        )


def test_overlong_conversation_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[{"role": "user", "content": "hi"}] * (MAX_MESSAGES + 1),
        )
