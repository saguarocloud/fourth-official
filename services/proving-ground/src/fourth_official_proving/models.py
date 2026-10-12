"""Running a configuration that drafts with models: the Analyst on Foundry, reading the benchmark
through a Match Data server of its own, and the price of every token it spends.

The Analyst reads the match through the Match Data MCP server's tools. The deployed server knows
only the demo matchday, so a run serves the benchmark from a server on loopback that lives exactly
as long as the run.
"""

import asyncio
import os
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import uvicorn

from fourth_official_explain.analyst import TokenCount
from fourth_official_match_data import MatchStore, create_server

LOOPBACK = "127.0.0.1"
STARTUP_SECONDS = 10.0
_POLL_SECONDS = 0.02
_PER_MILLION = 1_000_000
FOUNDRY_HOST_SUFFIX = ".services.ai.azure.com"


@dataclass(frozen=True, slots=True)
class Price:
    """US dollars per million tokens."""

    input: float
    output: float


# List prices of the models behind each alias (infra/main.bicep: fast is gpt-5-mini, fallback is
# gpt-4.1-mini; Global Standard, pay as you go). Change these with the deployments.
PRICES_PER_MILLION: dict[str, Price] = {
    "fast": Price(input=0.25, output=2.00),
    "fallback": Price(input=0.40, output=1.60),
}


@dataclass(slots=True)
class CostMeter:
    """Adds up what a run's model calls cost. An alias without a price is an error, never a
    guess: a scorecard's cost is either known or the run fails."""

    calls: int = 0
    _usd: float = field(default=0.0, repr=False)

    def __call__(self, spent: TokenCount) -> None:
        price = PRICES_PER_MILLION[spent.model]
        self._usd += (spent.input * price.input + spent.output * price.output) / _PER_MILLION
        self.calls += 1

    def cost_usd(self) -> float:
        return round(self._usd, 4)


class FoundryUnavailableError(RuntimeError):
    """A model run was asked for without a Foundry project to run it on."""


def project_endpoint() -> str:
    """The Foundry project to draft on, from FOUNDRY_PROJECT_ENDPOINT: an Azure AI Foundry
    project URL, never anywhere else (the run sends it the studio's credential)."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise FoundryUnavailableError("set FOUNDRY_PROJECT_ENDPOINT to run with models")
    parts = urlsplit(endpoint)
    host = parts.hostname or ""
    if parts.scheme != "https" or not host.endswith(FOUNDRY_HOST_SUFFIX):
        raise FoundryUnavailableError("FOUNDRY_PROJECT_ENDPOINT must be a Foundry project URL")
    return endpoint


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK, 0))
        return int(probe.getsockname()[1])


@asynccontextmanager
async def match_data_server(store: MatchStore) -> AsyncIterator[str]:
    """Serve `store` over streamable HTTP on loopback for the run; yields its MCP URL."""
    port = _free_port()
    app = create_server(store, host=LOOPBACK, port=port, version="proving-ground")
    server = uvicorn.Server(
        uvicorn.Config(app.streamable_http_app(), host=LOOPBACK, port=port, log_level="warning")
    )
    serving = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(STARTUP_SECONDS):
            while not server.started:
                if serving.done():
                    serving.result()
                await asyncio.sleep(_POLL_SECONDS)
        yield f"http://{LOOPBACK}:{port}/mcp"
    finally:
        server.should_exit = True
        await serving
