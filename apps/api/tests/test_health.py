import pytest
from fastapi.testclient import TestClient

from fourth_official_api.main import app_from_env, create_app
from fourth_official_api.settings import Settings


def _client(version: str = "test-sha") -> TestClient:
    return TestClient(create_app(Settings(version=version)))


def test_healthz_reports_ok_with_service_and_version() -> None:
    response = _client(version="abc1234").get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "fourth-official-api",
        "version": "abc1234",
    }


def test_healthz_is_not_cached() -> None:
    response = _client().get("/healthz")

    assert response.headers["cache-control"] == "no-store"


def test_unknown_route_returns_404() -> None:
    assert _client().get("/does-not-exist").status_code == 404


def test_app_from_env_wires_version_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "from-env")

    response = TestClient(app_from_env()).get("/healthz")

    assert response.json()["version"] == "from-env"
