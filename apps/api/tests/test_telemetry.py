"""Telemetry: traces and metrics go to Application Insights with the app's own identity, only
when the deployment names where to send them, and never with prompts or answers in them."""

from typing import Any

import pytest
from azure.identity import ManagedIdentityCredential
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

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
    # The app is instrumented by name, with its exclusions, not by the distro's import-time read.
    assert configured["instrumentation_options"] == {"fastapi": {"enabled": False}}


def test_a_destination_that_cannot_be_configured_leaves_the_api_running_without_telemetry(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(**_: object) -> None:
        raise ValueError("Invalid instrumentation key InstrumentationKey=secretish")

    monkeypatch.setattr(telemetry, "configure_azure_monitor", broken)

    assert telemetry.start(TelemetrySettings(connection_string="nonsense", client_id="")) is False
    assert "ValueError" in caplog.text
    assert "secretish" not in caplog.text


def test_the_api_starts_telemetry_then_traces_its_requests_but_not_probes_or_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[object] = []
    instrumented: list[dict[str, Any]] = []

    def start(settings: object) -> bool:
        started.append(settings)
        return True

    monkeypatch.setattr(telemetry, "start", start)
    monkeypatch.setattr(
        FastAPIInstrumentor,
        "instrument_app",
        lambda app, **kw: instrumented.append({"app": app, **kw}),
    )
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", CONNECTION)

    app = main.app_from_env()

    assert started == [Settings.from_env().telemetry]
    (call,) = instrumented
    assert call["app"] is app
    # Probes say nothing; a matchday stream is a span as long as its connection; and no span for
    # every chunk a response sends.
    assert call["excluded_urls"] == "healthz,stream"
    assert call["exclude_spans"] == ["send", "receive"]


def test_without_telemetry_the_app_is_not_instrumented(monkeypatch: pytest.MonkeyPatch) -> None:
    instrumented: list[object] = []
    monkeypatch.setattr(
        FastAPIInstrumentor, "instrument_app", lambda app, **kw: instrumented.append(app)
    )
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    main.app_from_env()

    assert instrumented == []
