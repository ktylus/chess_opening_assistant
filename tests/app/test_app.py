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
