"""Production: the prompts and models the live pipeline explains with. One definition, so the API
runs exactly what the Proving Ground gates (ADR-014): a pull request that changes a prompt version
or a model here is the candidate the Release Gate judges."""

from typing import Literal

from azure.core.credentials_async import AsyncTokenCredential

from fourth_official_explain.analyst import AgentDrafter, Meter, foundry_analyst
from fourth_official_explain.prompts import load_prompt

Effort = Literal["minimal", "low", "medium"]

ANALYST = ("analyst", "v1.2")
LOCALIZER = ("localizer", "v1.0")
# Model aliases in the order they are tried, with each one's reasoning effort.
MODELS: tuple[tuple[str, Effort | None], ...] = (
    ("fast", "minimal"),
    ("fallback", None),
)


def analyst_drafters(
    *,
    project_endpoint: str,
    match_data_url: str,
    credential: AsyncTokenCredential,
    prompt: tuple[str, str] = ANALYST,
    models: tuple[tuple[str, Effort | None], ...] = MODELS,
    meter: Meter | None = None,
) -> list[AgentDrafter]:
    """The Analyst on each model in turn. The caller owns `credential` and closes it after the
    drafters."""
    loaded = load_prompt(*prompt)
    return [
        foundry_analyst(
            project_endpoint=project_endpoint,
            deployment=alias,
            alias=alias,
            match_data_url=match_data_url,
            prompt=loaded,
            credential=credential,
            reasoning_effort=effort,
            meter=meter,
        )
        for alias, effort in models
    ]
