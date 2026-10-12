"""Model configurations: a local Match Data server over the benchmark, and what a run costs."""

import asyncio

import httpx
import pytest

from fourth_official_explain.analyst import TokenCount
from fourth_official_match_data import store_of
from fourth_official_proving.configurations import CONFIGURATIONS
from fourth_official_proving.models import (
    PRICES_PER_MILLION,
    CostMeter,
    FoundryUnavailableError,
    match_data_server,
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
