"""Runtime settings, read once from the environment at startup."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from fourth_official_replay.matchday import DEFAULT_RUNS_PER_DAY

DEFAULT_VERSION = "dev"
DEFAULT_REPLAY_SPEED = 8.0
MAX_REPLAY_SPEED = 120.0
# A Foundry project endpoint, and nothing else: the agents' credentials are only ever sent there.
FOUNDRY_ENDPOINT = re.compile(
    r"^https://[a-z0-9][a-z0-9-]{1,62}\.services\.ai\.azure\.com/api/projects/[A-Za-z0-9-]{2,64}$"
)
# The Match Data server: over HTTPS on an Azure Container Apps host, or plain HTTP on this machine.
MATCH_DATA_URL = re.compile(
    r"https://[a-z0-9][a-z0-9.-]{1,240}\.azurecontainerapps\.io/mcp"
    r"|http://(127\.0\.0\.1|localhost)(:[0-9]{1,5})?/mcp"
)

# One blob in Azure Storage, addressed without any key or signature: access is by identity.
START_LEDGER_URL = re.compile(
    r"https://[a-z0-9]{3,24}\.blob\.core\.windows\.net/[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])/"
    r"(?!\.{1,2}$)[A-Za-z0-9._-]{1,128}"
)


@dataclass(frozen=True, slots=True)
class PolicyBookSettings:
    """Where Policy Studio's book is kept, so edits survive restarts."""

    container_url: str
    # The client ID of the app's managed identity (empty: the developer's own credential).
    client_id: str


@dataclass(frozen=True, slots=True)
class StartLedgerSettings:
    """Where the matchday's starts are kept, so its spend guards survive restarts."""

    url: str
    # The client ID of the app's managed identity (empty: the developer's own credential).
    client_id: str


@dataclass(frozen=True, slots=True)
class FoundrySettings:
    """Where the Analyst runs, and where it reads the match."""

    project_endpoint: str
    match_data_url: str
    # The client ID of the agents' managed identity (empty: the developer's own credential).
    client_id: str


@dataclass(frozen=True, slots=True)
class ProvenanceSettings:
    """The studio's signing key (a Key Vault key version) and where signed records are kept."""

    key_id: str
    container_url: str
    # The client ID of the app's managed identity (empty: the developer's own credential).
    client_id: str


@dataclass(frozen=True, slots=True)
class TelemetrySettings:
    """Where to send traces and metrics (Application Insights), and as whom."""

    connection_string: str
    # The client ID of the app's managed identity (empty: the system-assigned one).
    client_id: str


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime configuration for the API."""

    version: str
    # None: explain with the deterministic templates alone.
    foundry: FoundrySettings | None = None
    # How many times faster than real time the matchday replays.
    replay_speed: float = DEFAULT_REPLAY_SPEED
    # None: starts are kept in memory, which only template runs (costing nothing) may rely on.
    start_ledger: StartLedgerSettings | None = None
    # How many matchday runs may start in any 24 hours: the ceiling on model spend per day.
    runs_per_day: int = DEFAULT_RUNS_PER_DAY
    # None: records are signed with a key that lives as long as the process, and kept in memory.
    provenance: ProvenanceSettings | None = None
    # None: the policy book is kept in memory and resets with the process.
    policy_book: PolicyBookSettings | None = None
    # The Proving Ground's recorded runs, served read-only (relative to the working directory).
    proving_results: Path = Path("eval/results")
    # None: no telemetry leaves the process.
    telemetry: TelemetrySettings | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Read settings from environment variables, applying defaults for unset values."""
        # APP_VERSION is the git SHA injected by the deploy pipeline.
        version = os.environ.get("APP_VERSION", "").strip()
        return cls(
            version=version or DEFAULT_VERSION,
            foundry=_foundry_from_env(),
            replay_speed=_speed_from_env(),
            start_ledger=_ledger_from_env(),
            runs_per_day=_runs_from_env(),
            provenance=_provenance_from_env(),
            policy_book=_policy_book_from_env(),
            telemetry=_telemetry_from_env(),
            proving_results=Path(
                os.environ.get("PROVING_RESULTS_DIR", "").strip() or "eval/results"
            ),
        )


def _foundry_from_env() -> FoundrySettings | None:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    url = os.environ.get("MATCH_DATA_URL", "").strip()
    if not endpoint and not url:
        return None
    if not FOUNDRY_ENDPOINT.fullmatch(endpoint):
        raise ValueError("FOUNDRY_PROJECT_ENDPOINT must be a Foundry project endpoint")
    if not MATCH_DATA_URL.fullmatch(url):
        raise ValueError("MATCH_DATA_URL must be the Match Data server's /mcp URL")
    return FoundrySettings(
        project_endpoint=endpoint,
        match_data_url=url,
        client_id=os.environ.get("AZURE_CLIENT_ID", "").strip(),
    )


def _speed_from_env() -> float:
    raw = os.environ.get("REPLAY_SPEED", "").strip()
    if not raw:
        return DEFAULT_REPLAY_SPEED
    try:
        speed = float(raw)
    except ValueError:
        raise ValueError("REPLAY_SPEED must be a number") from None
    if not 1.0 <= speed <= MAX_REPLAY_SPEED:
        raise ValueError(f"REPLAY_SPEED must be between 1 and {MAX_REPLAY_SPEED:g}")
    return speed


def _policy_book_from_env() -> PolicyBookSettings | None:
    url = os.environ.get("POLICY_BOOK_URL", "").strip()
    if not url:
        return None
    if not CONTAINER_URL.fullmatch(url):
        raise ValueError("POLICY_BOOK_URL must be a container URL in Azure Storage, no query")
    return PolicyBookSettings(
        container_url=url, client_id=os.environ.get("AZURE_CLIENT_ID", "").strip()
    )


def _ledger_from_env() -> StartLedgerSettings | None:
    url = os.environ.get("START_LEDGER_URL", "").strip()
    if not url:
        return None
    if not START_LEDGER_URL.fullmatch(url):
        raise ValueError("START_LEDGER_URL must be a blob URL in Azure Storage, without a query")
    return StartLedgerSettings(url=url, client_id=os.environ.get("AZURE_CLIENT_ID", "").strip())


KEY_VERSION_ID = re.compile(
    r"https://[a-z0-9-]{3,24}\.vault\.azure\.net/keys/[A-Za-z0-9-]{1,127}/[0-9a-f]{32}"
)
CONTAINER_URL = re.compile(
    r"https://[a-z0-9]{3,24}\.blob\.core\.windows\.net/[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])"
)


def _provenance_from_env() -> ProvenanceSettings | None:
    key_id = os.environ.get("PROVENANCE_KEY_ID", "").strip()
    container = os.environ.get("PROVENANCE_CONTAINER_URL", "").strip()
    if not key_id and not container:
        return None
    if not KEY_VERSION_ID.fullmatch(key_id):
        raise ValueError("PROVENANCE_KEY_ID must be a Key Vault key, with its version")
    if not CONTAINER_URL.fullmatch(container):
        raise ValueError("PROVENANCE_CONTAINER_URL must be a container in Azure Storage, no query")
    return ProvenanceSettings(
        key_id=key_id,
        container_url=container,
        # The signer identity: the API's own for signing, never the one that talks to the models.
        client_id=os.environ.get("PROVENANCE_CLIENT_ID", "").strip(),
    )


def _runs_from_env() -> int:
    raw = os.environ.get("MATCHDAY_RUNS_PER_DAY", "").strip()
    if not raw:
        return DEFAULT_RUNS_PER_DAY
    if not raw.isdigit() or not 1 <= int(raw) <= DEFAULT_RUNS_PER_DAY:
        raise ValueError(
            f"MATCHDAY_RUNS_PER_DAY must be a whole number from 1 to {DEFAULT_RUNS_PER_DAY}"
        )
    return int(raw)


def _telemetry_from_env() -> TelemetrySettings | None:
    connection = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not connection:
        return None
    return TelemetrySettings(
        connection_string=connection, client_id=os.environ.get("AZURE_CLIENT_ID", "").strip()
    )
