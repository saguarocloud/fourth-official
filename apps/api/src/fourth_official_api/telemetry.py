"""Telemetry to Application Insights (ADR-017): the API's requests, the Agent Framework's model
and tool calls, and the replay's own spans (a moment explained, each partner's localisation).

Sent only where the deployment names a destination, signed in as the app's own identity (the
component accepts nothing else), and never with what the models read or wrote: spans carry
identifiers, outcomes and timings, not prompts or answers. Logs are not exported (an exception's
text can quote a model's output); they stay in the console, which Log Analytics keeps.
"""

import logging
from typing import Literal

from agent_framework.observability import enable_instrumentation
from azure.identity import ManagedIdentityCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import TracerProvider

from fourth_official_api.settings import TelemetrySettings

logger = logging.getLogger(__name__)
# Health probes would be most of the requests traced, and say nothing; a matchday stream is a
# span as long as the connection. Neither is traced, nor each chunk a response sends.
# Patterns searched in the full URL: anchored to the path's end, so a query string or a host that
# merely contains the word is still traced.
EXCLUDED_URLS = r"/healthz(\?|$),/stream(\?|$)"
EXCLUDED_SPANS: list[Literal["send", "receive"]] = ["send", "receive"]


def start(settings: TelemetrySettings | None) -> bool:
    """Configure the exporters once, at process start; whether telemetry is on."""
    if settings is None:
        return False
    try:
        configure_azure_monitor(
            connection_string=settings.connection_string,
            credential=ManagedIdentityCredential(client_id=settings.client_id or None),
            disable_logging=True,
            enable_live_metrics=False,
            # The app is instrumented by `instrument`, with its exclusions as arguments: the
            # distro's own instrumentation reads them from the environment at import, too early.
            instrumentation_options={"fastapi": {"enabled": False}},
        )
    except Exception as error:
        # Telemetry must never stop the API.
        # The type only: the message can quote the connection string.
        logger.error(
            "telemetry could not be configured (%s); running without it", type(error).__name__
        )
        return False
    enable_instrumentation(enable_sensitive_data=False)
    logger.info("telemetry is sent to Application Insights")
    return True


def instrument(app: FastAPI, *, tracer_provider: TracerProvider | None = None) -> None:
    """Trace the app's requests, but not probes, the matchday streams or every chunk sent (to
    the global provider unless one is given)."""
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls=EXCLUDED_URLS,
        exclude_spans=EXCLUDED_SPANS,
        tracer_provider=tracer_provider,
    )
