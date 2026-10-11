import dataclasses

import pytest

from fourth_official_api.settings import Settings


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
