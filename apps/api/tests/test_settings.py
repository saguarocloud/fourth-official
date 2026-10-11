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
