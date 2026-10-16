"""Telemetry to Application Insights (ADR-017): the API's requests, the Agent Framework's model
and tool calls, and the replay's own spans (a moment explained, each partner's localisation).

Sent only where the deployment names a destination, signed in as the app's own identity (the
component accepts nothing else), and never with what the models read or wrote: spans carry
identifiers, outcomes and timings, not prompts or answers. Logs are not exported (an exception's
text can quote a model's output); they stay in the console, which Log Analytics keeps.
"""

import logging
import os

from agent_framework.observability import enable_instrumentation
from azure.identity import ManagedIdentityCredential
from azure.monitor.opentelemetry import configure_azure_monitor

from fourth_official_api.settings import TelemetrySettings

logger = logging.getLogger(__name__)
# Health probes would be most of the requests traced, and say nothing; a matchday stream is a
# span as long as the connection. Neither is traced, nor each chunk a response sends.
EXCLUDED_URLS = "healthz,stream"
EXCLUDED_SPANS = "send,receive"


def start(settings: TelemetrySettings | None) -> bool:
    """Configure the exporters once, at process start; whether telemetry is on."""
    if settings is None:
        return False
    os.environ.setdefault("OTEL_PYTHON_FASTAPI_EXCLUDED_URLS", EXCLUDED_URLS)
    os.environ.setdefault("OTEL_PYTHON_FASTAPI_EXCLUDE_SPANS", EXCLUDED_SPANS)
    try:
        configure_azure_monitor(
            connection_string=settings.connection_string,
            credential=ManagedIdentityCredential(client_id=settings.client_id or None),
            disable_logging=True,
            enable_live_metrics=False,
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
