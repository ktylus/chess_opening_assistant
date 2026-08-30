from fastapi.testclient import TestClient

from backend.app.app import create_app


class FakeClient:
    async def stream(self, chat_request):
        yield "test response"


def test_lifespan_creates_one_shared_client():
    created = []

    def client_factory():
        client = FakeClient()
        created.append(client)
        return client

    app = create_app(client_factory)  # type: ignore[arg-type]

    with TestClient(app) as test_client:
        assert app.state.client is created[0]
        assert test_client.get("/health").json() == {"status": "ok"}
        response = test_client.post("/chat", json={"messages": [], "pgn": ""})

    assert response.text == "test response"
    assert len(created) == 1
