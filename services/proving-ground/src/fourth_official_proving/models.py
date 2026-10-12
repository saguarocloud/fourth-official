"""Running a configuration that drafts with models: the Analyst on Foundry, reading the benchmark
through a Match Data server of its own, and the price of every token it spends.

The Analyst reads the match through the Match Data MCP server's tools. The deployed server knows
only the demo matchday, so a run serves the benchmark from a server on loopback that lives exactly
as long as the run.
"""

import asyncio
import os
import re
import socket
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from http import HTTPStatus
from types import MappingProxyType
from typing import Protocol
from urllib.parse import urlsplit

import httpx
import uvicorn

from fourth_official_explain.analyst import TokenCount
from fourth_official_match_data import MatchStore, create_server

LOOPBACK = "127.0.0.1"
STARTUP_SECONDS = 10.0
SHUTDOWN_SECONDS = 5
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
PRICES_PER_MILLION: Mapping[str, Price] = MappingProxyType(
    {
        "fast": Price(input=0.25, output=2.00),
        "fallback": Price(input=0.40, output=1.60),
    }
)


@dataclass(slots=True)
class CostMeter:
    """Adds up what a run's model calls cost. An alias without a price is an error, never a
    guess: a scorecard's cost is either known or the run fails."""

    calls: int = 0
    _usd: float = field(default=0.0, init=False, repr=False)

    def __call__(self, spent: TokenCount) -> None:
        price = PRICES_PER_MILLION[spent.model]
        self._usd += (spent.input * price.input + spent.output * price.output) / _PER_MILLION
        self.calls += 1

    def cost_usd(self) -> float | None:
        """The run's cost, or None if no call reported what it spent (unknown, not free)."""
        return round(self._usd, 4) if self.calls else None


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


# The scope the Foundry project endpoint accepts (as azure-ai-projects uses).
FOUNDRY_SCOPE = "https://ai.azure.com/.default"
PREFLIGHT_MODEL = "fast"
PREFLIGHT_SECONDS = 60.0
_MAX_REASON = 300
_IDENTIFIER = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")


class AccessTokenLike(Protocol):
    @property
    def token(self) -> str: ...


class TokenSource(Protocol):
    async def get_token(self, *scopes: str) -> AccessTokenLike: ...


def _reason(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
        reason = f"{error.get('code', '')}: {error.get('message', '')}"
    except (ValueError, AttributeError):
        reason = response.text
    # Foundry names the principal it refused: an identifier, kept out of public CI logs.
    return _IDENTIFIER.sub("<id>", reason)[:_MAX_REASON]


async def preflight(
    endpoint: str,
    credential: TokenSource,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    """One small call to the first model before a run, so a run the models refuse stops at once
    with Foundry's own reason (which names any permission missing), not after every draft."""
    token = await credential.get_token(FOUNDRY_SCOPE)
    async with httpx.AsyncClient(transport=transport, timeout=PREFLIGHT_SECONDS) as client:
        response = await client.post(
            f"{endpoint.rstrip('/')}/openai/v1/responses",
            headers={"Authorization": f"Bearer {token.token}"},
            json={"model": PREFLIGHT_MODEL, "input": "Reply with OK.", "max_output_tokens": 16},
        )
    if response.status_code >= HTTPStatus.BAD_REQUEST:
        raise FoundryUnavailableError(
            f"the models refused the preflight call: {response.status_code} {_reason(response)}"
        )


class _QuietServer(uvicorn.Server):
    # The run owns Ctrl-C and SIGTERM, not the server inside it.
    def install_signal_handlers(self) -> None:
        return None


@asynccontextmanager
async def match_data_server(store: MatchStore) -> AsyncIterator[str]:
    """Serve `store` over streamable HTTP on loopback for the run; yields its MCP URL. The socket
    is bound here and handed to the server, so no other process can take the port in between."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOOPBACK, 0))
        port = int(sock.getsockname()[1])
        app = create_server(store, host=LOOPBACK, port=port, version="proving-ground")
        server = _QuietServer(
            uvicorn.Config(
                app.streamable_http_app(),
                log_level="warning",
                timeout_graceful_shutdown=SHUTDOWN_SECONDS,
            )
        )
        serving = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(STARTUP_SECONDS):
                while not server.started:
                    if serving.done():
                        serving.result()
                    await asyncio.sleep(_POLL_SECONDS)
            yield f"http://{LOOPBACK}:{port}/mcp"
        finally:
            server.should_exit = True
            try:
                async with asyncio.timeout(SHUTDOWN_SECONDS * 2):
                    await serving
            except TimeoutError:
                serving.cancel()
