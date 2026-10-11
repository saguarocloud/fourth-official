"""Runtime settings, read once from the environment at startup."""

import os
import re
from dataclasses import dataclass

DEFAULT_VERSION = "dev"
# A Foundry project endpoint, and nothing else: the agents' credentials are only ever sent there.
FOUNDRY_ENDPOINT = re.compile(
    r"^https://[a-z0-9][a-z0-9-]{1,62}\.services\.ai\.azure\.com/api/projects/[A-Za-z0-9-]{2,64}$"
)
MATCH_DATA_URL = re.compile(r"^https?://[A-Za-z0-9.-]{1,253}(:[0-9]{1,5})?/mcp$")


@dataclass(frozen=True, slots=True)
class FoundrySettings:
    """Where the Analyst runs, and where it reads the match."""

    project_endpoint: str
    match_data_url: str
    # The client ID of the agents' managed identity (empty: the developer's own credential).
    client_id: str


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime configuration for the API."""

    version: str
    # None: explain with the deterministic templates alone.
    foundry: FoundrySettings | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Read settings from environment variables, applying defaults for unset values."""
        # APP_VERSION is the git SHA injected by the deploy pipeline.
        version = os.environ.get("APP_VERSION", "").strip()
        return cls(version=version or DEFAULT_VERSION, foundry=_foundry_from_env())


def _foundry_from_env() -> FoundrySettings | None:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    url = os.environ.get("MATCH_DATA_URL", "").strip()
    if not endpoint and not url:
        return None
    if not FOUNDRY_ENDPOINT.match(endpoint):
        raise ValueError("FOUNDRY_PROJECT_ENDPOINT must be a Foundry project endpoint")
    if not MATCH_DATA_URL.match(url):
        raise ValueError("MATCH_DATA_URL must be the Match Data server's /mcp URL")
    return FoundrySettings(
        project_endpoint=endpoint,
        match_data_url=url,
        client_id=os.environ.get("AZURE_CLIENT_ID", "").strip(),
    )
