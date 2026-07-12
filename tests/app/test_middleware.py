import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from backend.app.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from backend.observability import current_event, get_request_id


@pytest.fixture
def test_client():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/echo")
    async def echo():
        return {"request_id": get_request_id()}

    @app.get("/stream")
    async def stream():
        async def body():
            # The identifiers and the event have to survive into the streaming
            # body, which runs after the endpoint has already returned.
            current_event().chars_streamed = 7
            yield f"{get_request_id()}:{current_event().chars_streamed}"

        return StreamingResponse(body(), media_type="text/plain")

    return TestClient(app)


def test_request_id_is_minted_and_echoed_back(test_client):
    response = test_client.get("/echo")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert request_id
    assert response.json()["request_id"] == request_id


def test_inbound_request_id_is_honoured(test_client):
    response = test_client.get("/echo", headers={REQUEST_ID_HEADER: "from-proxy"})

    assert response.headers[REQUEST_ID_HEADER] == "from-proxy"
    assert response.json()["request_id"] == "from-proxy"


def test_each_request_gets_its_own_id(test_client):
    first = test_client.get("/echo").headers[REQUEST_ID_HEADER]
    second = test_client.get("/echo").headers[REQUEST_ID_HEADER]

    assert first != second


def test_context_reaches_the_streaming_body(test_client):
    response = test_client.get("/stream")

    assert response.text == f"{response.headers[REQUEST_ID_HEADER]}:7"
