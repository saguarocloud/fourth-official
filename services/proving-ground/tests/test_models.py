"""Model configurations: a local Match Data server over the benchmark, and what a run costs."""

import asyncio
import json

import httpx
import pytest
from azure.core.credentials import AccessToken

from fourth_official_explain.metering import TokenCount
from fourth_official_match_data import store_of
from fourth_official_proving.configurations import CONFIGURATIONS
from fourth_official_proving.models import (
    PRICES_PER_MILLION,
    CostMeter,
    FoundryUnavailableError,
    match_data_server,
    preflight,
    project_endpoint,
)
from fourth_official_simulator.benchmark import benchmark_matches


def test_the_benchmark_is_served_locally_for_the_analysts_tools() -> None:
    async def probe() -> tuple[str, int, int]:
        async with match_data_server(store_of(benchmark_matches(1))) as url:
            async with httpx.AsyncClient() as client:
                health = await client.get(url.removesuffix("/mcp") + "/healthz")
                foreign = await client.get(url, headers={"Host": "evil.example"})
            return url, health.status_code, foreign.status_code

    url, health, foreign = asyncio.run(probe())

    assert url.startswith("http://127.0.0.1:")
    assert url.endswith("/mcp")
    assert health == 200
    assert foreign == 421


def test_the_server_stops_when_the_run_ends() -> None:
    async def served() -> str:
        async with match_data_server(store_of(benchmark_matches(1))) as url:
            return url

    url = asyncio.run(served())
    with pytest.raises(httpx.ConnectError):
        httpx.get(url.removesuffix("/mcp") + "/healthz", timeout=2)


def test_tokens_are_priced_by_the_model_behind_each_alias() -> None:
    meter = CostMeter()
    meter(TokenCount(model="fast", input=1_000_000, output=100_000))
    meter(TokenCount(model="fallback", input=500_000, output=0))

    fast, fallback = PRICES_PER_MILLION["fast"], PRICES_PER_MILLION["fallback"]
    expected = fast.input + fast.output / 10 + fallback.input / 2
    assert meter.cost_usd() == pytest.approx(expected)
    assert meter.calls == 2


def test_an_alias_without_a_price_is_refused_not_guessed() -> None:
    with pytest.raises(KeyError):
        CostMeter()(TokenCount(model="unknown", input=1, output=1))


def test_a_model_run_needs_the_foundry_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)

    with pytest.raises(FoundryUnavailableError, match="FOUNDRY_PROJECT_ENDPOINT"):
        project_endpoint()


def test_only_an_azure_foundry_project_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://attacker.example/api/projects/x")

    with pytest.raises(FoundryUnavailableError):
        project_endpoint()


def test_production_and_the_candidate_differ_only_in_the_analysts_prompt() -> None:
    production = CONFIGURATIONS["production"].configuration
    candidate = CONFIGURATIONS["candidate"].configuration

    assert production.analyst_prompt == "analyst/v1.2"
    assert candidate.analyst_prompt == "analyst/v1.4"
    assert production.models == candidate.models == ("fast", "fallback")
    assert production.localizer_prompt == candidate.localizer_prompt == "template"


def test_the_server_stops_even_when_the_run_fails() -> None:
    async def failing() -> str:
        async with match_data_server(store_of(benchmark_matches(1))) as url:
            raise RuntimeError(url)

    with pytest.raises(RuntimeError) as failed:
        asyncio.run(failing())
    with pytest.raises(httpx.ConnectError):
        httpx.get(str(failed.value).removesuffix("/mcp") + "/healthz", timeout=2)


def test_a_meter_that_heard_of_no_call_knows_no_cost() -> None:
    assert CostMeter().cost_usd() is None


class FixedToken:
    async def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        assert scopes == ("https://ai.azure.com/.default",)
        return AccessToken("t0ken", 0)


ENDPOINT = "https://ais-x.services.ai.azure.com/api/projects/proj"


def answering(status: int, body: object) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/projects/proj/openai/v1/responses"
        assert request.headers["authorization"] == "Bearer t0ken"
        assert json.loads(request.content)["model"] == "fast"
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


def test_the_preflight_passes_when_the_model_answers() -> None:
    asyncio.run(preflight(ENDPOINT, FixedToken(), transport=answering(200, {"id": "resp_1"})))


def test_a_refusal_stops_the_run_with_foundrys_reason_and_no_identifiers() -> None:
    body = {
        "error": {
            "code": "PermissionDenied",
            "message": "The principal `0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b` lacks the required "
            "data action `Microsoft.CognitiveServices/accounts/AIServices/responses/write`.",
        }
    }

    with pytest.raises(FoundryUnavailableError) as refused:
        asyncio.run(preflight(ENDPOINT, FixedToken(), transport=answering(403, body)))

    message = str(refused.value)
    assert "403 PermissionDenied" in message
    assert "AIServices/responses/write" in message
    assert "0f1e2d3c" not in message


def test_model_runs_replay_fewer_matches_at_once_than_template_runs() -> None:
    # The deployments' token-per-minute limits refuse four matches' drafts at once (429).
    assert CONFIGURATIONS["production"].concurrency == 2
    assert CONFIGURATIONS["candidate"].concurrency == 2
    assert CONFIGURATIONS["template"].concurrency == 4
