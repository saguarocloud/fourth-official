"""Telemetry to Application Insights (ADR-017): the API's requests, the Agent Framework's model
and tool calls, and the replay's own spans (a moment explained, each partner's localisation).

Sent only where the deployment names a destination, signed in as the app's own identity (the
component accepts nothing else), and never with what the models read or wrote: spans carry
identifiers, outcomes and timings, not prompts or answers.
"""

import logging
import os

from agent_framework.observability import enable_instrumentation
from azure.identity import ManagedIdentityCredential
from azure.monitor.opentelemetry import configure_azure_monitor

from fourth_official_api.settings import TelemetrySettings

logger = logging.getLogger(__name__)
# Health probes would be most of the requests traced, and say nothing.
EXCLUDED_URLS = "healthz"


def start(settings: TelemetrySettings | None) -> bool:
    """Configure the exporters once, at process start; whether telemetry is on."""
    if settings is None:
        return False
    os.environ.setdefault("OTEL_PYTHON_FASTAPI_EXCLUDED_URLS", EXCLUDED_URLS)
    configure_azure_monitor(
        connection_string=settings.connection_string,
        credential=ManagedIdentityCredential(client_id=settings.client_id or None),
        logger_name="fourth_official",
    )
    enable_instrumentation(enable_sensitive_data=False)
    logger.info("telemetry is sent to Application Insights")
    return True
