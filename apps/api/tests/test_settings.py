import dataclasses

import pytest

from fourth_official_api.settings import Settings
from fourth_official_replay.matchday import DEFAULT_RUNS_PER_DAY


def test_version_comes_from_app_version_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "9f8e7d6")

    assert Settings.from_env().version == "9f8e7d6"


def test_version_defaults_to_dev_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_VERSION", raising=False)

    assert Settings.from_env().version == "dev"


def test_blank_version_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "   ")

    assert Settings.from_env().version == "dev"


def test_settings_are_immutable() -> None:
    settings = Settings(version="x")

    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.version = "y"  # type: ignore[misc]


ENDPOINT = "https://ais-abc.services.ai.azure.com/api/projects/proj-fourth-official"


def test_without_foundry_the_api_explains_with_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("FOUNDRY_PROJECT_ENDPOINT", "MATCH_DATA_URL", "AZURE_CLIENT_ID"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.foundry is None


def test_foundry_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", ENDPOINT)
    monkeypatch.setenv(
        "MATCH_DATA_URL", "https://ca-match-data.internal.x.eastus2.azurecontainerapps.io/mcp"
    )
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-0000-0000-000000000001")

    foundry = Settings.from_env().foundry

    assert foundry is not None
    assert (foundry.project_endpoint, foundry.match_data_url) == (
        ENDPOINT,
        "https://ca-match-data.internal.x.eastus2.azurecontainerapps.io/mcp",
    )
    assert foundry.client_id == "00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize(
    ("endpoint", "url"),
    [
        (
            "http://ais-abc.services.ai.azure.com/api/projects/p",
            "https://ca-match-data.internal.x.eastus2.azurecontainerapps.io/mcp",
        ),
        (
            "https://evil.example/api/projects/p",
            "https://ca-match-data.internal.x.eastus2.azurecontainerapps.io/mcp",
        ),
        (ENDPOINT, "ftp://ca-match-data/mcp"),
        (ENDPOINT, ""),
        (ENDPOINT, "http://169.254.169.254/mcp"),
        (ENDPOINT, "http://ca-match-data.internal.x.eastus2.azurecontainerapps.io/mcp"),
        (ENDPOINT, "https://evil.example/mcp"),
    ],
)
def test_foundry_settings_are_validated(
    monkeypatch: pytest.MonkeyPatch, endpoint: str, url: str
) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", endpoint)
    monkeypatch.setenv("MATCH_DATA_URL", url)

    with pytest.raises(ValueError, match=r"FOUNDRY_PROJECT_ENDPOINT|MATCH_DATA_URL"):
        Settings.from_env()


def test_plain_http_is_allowed_only_on_this_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("MATCH_DATA_URL", "http://127.0.0.1:8100/mcp")

    foundry = Settings.from_env().foundry

    assert foundry is not None
    assert foundry.match_data_url == "http://127.0.0.1:8100/mcp"


def test_replay_speed_defaults_and_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REPLAY_SPEED", raising=False)
    assert Settings.from_env().replay_speed == 8.0

    monkeypatch.setenv("REPLAY_SPEED", "30")
    assert Settings.from_env().replay_speed == 30.0


@pytest.mark.parametrize("value", ["fast", "0", "0.5", "1000"])
def test_replay_speed_is_validated(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("REPLAY_SPEED", value)

    with pytest.raises(ValueError, match="REPLAY_SPEED"):
        Settings.from_env()


LEDGER = "https://stfoabc123.blob.core.windows.net/matchday/starts.json"


def test_the_start_ledger_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("START_LEDGER_URL", LEDGER)
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-0000-0000-000000000001")

    ledger = Settings.from_env().start_ledger

    assert ledger is not None
    assert (ledger.url, ledger.client_id) == (LEDGER, "00000000-0000-0000-0000-000000000001")


def test_without_a_start_ledger_url_there_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("START_LEDGER_URL", raising=False)

    assert Settings.from_env().start_ledger is None


@pytest.mark.parametrize(
    "url",
    [
        "http://stfoabc123.blob.core.windows.net/matchday/starts.json",
        "https://evil.example/matchday/starts.json",
        "https://stfoabc123.blob.core.windows.net.evil.example/matchday/starts.json",
        "https://stfoabc123.blob.core.windows.net/matchday/starts.json?sig=x",
        "https://stfoabc123.blob.core.windows.net/matchday",
        "https://stfoabc123.blob.core.windows.net/matchday/..",
    ],
)
def test_a_start_ledger_url_must_be_a_blob_in_azure_storage(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("START_LEDGER_URL", url)

    with pytest.raises(ValueError, match="START_LEDGER_URL"):
        Settings.from_env()


def test_the_daily_allowance_of_runs_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATCHDAY_RUNS_PER_DAY", "6")

    assert Settings.from_env().runs_per_day == 6


def test_the_daily_allowance_defaults_to_the_matchday_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MATCHDAY_RUNS_PER_DAY", raising=False)

    assert Settings.from_env().runs_per_day == DEFAULT_RUNS_PER_DAY


@pytest.mark.parametrize("value", ["0", "25", "six", "1.5"])
def test_the_daily_allowance_must_be_a_whole_number_up_to_the_default(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("MATCHDAY_RUNS_PER_DAY", value)

    with pytest.raises(ValueError, match="MATCHDAY_RUNS_PER_DAY"):
        Settings.from_env()


KEY_ID = "https://kv-abc123.vault.azure.net/keys/provenance/0123456789abcdef0123456789abcdef"
RECORDS = "https://stabc123.blob.core.windows.net/provenance"


def test_provenance_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVENANCE_KEY_ID", KEY_ID)
    monkeypatch.setenv("PROVENANCE_CONTAINER_URL", RECORDS)
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-1")

    provenance = Settings.from_env().provenance

    assert provenance is not None
    assert (provenance.key_id, provenance.container_url, provenance.client_id) == (
        KEY_ID,
        RECORDS,
        "client-1",
    )


def test_without_provenance_settings_records_stay_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVENANCE_KEY_ID", raising=False)
    monkeypatch.delenv("PROVENANCE_CONTAINER_URL", raising=False)

    assert Settings.from_env().provenance is None


@pytest.mark.parametrize(
    ("key_id", "container"),
    [
        (KEY_ID, ""),  # half configured
        ("", RECORDS),
        ("https://evil.example/keys/provenance/1", RECORDS),
        (KEY_ID, "https://stabc123.blob.core.windows.net/provenance?sv=1"),
        ("https://kv-abc123.vault.azure.net/keys/provenance", RECORDS),  # no version
    ],
)
def test_provenance_settings_must_name_a_vault_key_version_and_a_container(
    monkeypatch: pytest.MonkeyPatch, key_id: str, container: str
) -> None:
    monkeypatch.setenv("PROVENANCE_KEY_ID", key_id)
    monkeypatch.setenv("PROVENANCE_CONTAINER_URL", container)

    with pytest.raises(ValueError, match="PROVENANCE"):
        Settings.from_env()
