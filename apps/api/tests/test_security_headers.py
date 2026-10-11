"""Every API response carries the browser protections; JSON answers forbid everything else."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.types import Receive, Scope, Send

from fourth_official_api.main import create_app
from fourth_official_api.security import SecurityHeaders
from fourth_official_api.settings import Settings

PROTECTIONS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "strict-transport-security": "max-age=63072000; includeSubDomains",
    "cross-origin-resource-policy": "same-origin",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(version="test"))) as client:
        yield client


@pytest.mark.parametrize("path", ["/healthz", "/api/matches", "/does-not-exist"])
def test_every_response_carries_the_protections(client: TestClient, path: str) -> None:
    headers = client.get(path).headers

    for name, value in PROTECTIONS.items():
        assert headers[name] == value, name
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/docs/oauth2-redirect"])
def test_the_api_docs_keep_the_protections_but_may_load_their_assets(
    client: TestClient, path: str
) -> None:
    headers = client.get(path).headers

    assert headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in headers


def test_a_header_a_route_set_is_replaced_never_duplicated() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"x-frame-options", b"SAMEORIGIN"), (b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    response = TestClient(SecurityHeaders(app)).get("/")

    assert response.headers.get_list("x-frame-options") == ["DENY"]
    assert response.headers["content-type"] == "text/plain"
