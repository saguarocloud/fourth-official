"""Telemetry: traces and metrics go to Application Insights with the app's own identity, only
when the deployment names where to send them, and never with prompts or answers in them."""

import os
from typing import Any

import pytest
from azure.identity import ManagedIdentityCredential

from fourth_official_api import main, telemetry
from fourth_official_api.settings import Settings, TelemetrySettings

CONNECTION = "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://example.in.applicationinsights.azure.com/"


def test_telemetry_is_configured_only_where_the_deployment_names_a_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    assert Settings.from_env().telemetry is None

    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", f" {CONNECTION} ")
    monkeypatch.setenv("AZURE_CLIENT_ID", "11111111-1111-1111-1111-111111111111")
    assert Settings.from_env().telemetry == TelemetrySettings(
        connection_string=CONNECTION, client_id="11111111-1111-1111-1111-111111111111"
    )


def test_nothing_is_sent_without_a_destination() -> None:
    assert telemetry.start(None) is False


def test_telemetry_signs_in_as_the_app_and_never_records_what_the_models_read_or_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_PYTHON_FASTAPI_EXCLUDED_URLS", raising=False)
    monkeypatch.delenv("OTEL_PYTHON_FASTAPI_EXCLUDE_SPANS", raising=False)
    configured: dict[str, Any] = {}
    instrumented: dict[str, Any] = {}
    monkeypatch.setattr(telemetry, "configure_azure_monitor", lambda **kw: configured.update(kw))
    monkeypatch.setattr(telemetry, "enable_instrumentation", lambda **kw: instrumented.update(kw))

    started = telemetry.start(
        TelemetrySettings(
            connection_string=CONNECTION, client_id="11111111-1111-1111-1111-111111111111"
        )
    )

    assert started is True
    assert configured["connection_string"] == CONNECTION
    assert isinstance(configured["credential"], ManagedIdentityCredential)
    assert instrumented == {"enable_sensitive_data": False}
    # Logs stay in the console (Log Analytics): an exception's text can quote a model's output.
    assert configured["disable_logging"] is True
    assert configured["enable_live_metrics"] is False
    # Probes and the matchday streams (a span the length of a connection) are not traced, nor is
    # every chunk a stream sends.
    assert os.environ["OTEL_PYTHON_FASTAPI_EXCLUDED_URLS"] == "healthz,stream"
    assert os.environ["OTEL_PYTHON_FASTAPI_EXCLUDE_SPANS"] == "send,receive"


def test_a_destination_that_cannot_be_configured_leaves_the_api_running_without_telemetry(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(**_: object) -> None:
        raise ValueError("Invalid instrumentation key InstrumentationKey=secretish")

    monkeypatch.setattr(telemetry, "configure_azure_monitor", broken)

    assert telemetry.start(TelemetrySettings(connection_string="nonsense", client_id="")) is False
    assert "ValueError" in caplog.text
    assert "secretish" not in caplog.text


def test_the_api_starts_telemetry_before_it_is_built(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[object] = []
    monkeypatch.setattr(telemetry, "start", started.append)
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", CONNECTION)

    main.app_from_env()

    assert started == [Settings.from_env().telemetry]
