"""How the API explains moments: the Analyst on Foundry when configured, else templates alone."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal

from azure.identity.aio import DefaultAzureCredential

from fourth_official_api.settings import FoundrySettings
from fourth_official_contracts import Moment
from fourth_official_explain import Explanation, explain
from fourth_official_explain.analyst import AgentDrafter, foundry_analyst
from fourth_official_explain.prompts import load_prompt
from fourth_official_replay import Explainer
from fourth_official_verifier import MatchFacts

PROMPT = ("analyst", "v1.1")
# Model aliases in the order they are tried, with each one's reasoning effort.
MODELS: tuple[tuple[str, Literal["minimal", "low", "medium"] | None], ...] = (
    ("fast", "minimal"),
    ("fallback", None),
)


async def template_explainer(moment: Moment, facts: MatchFacts) -> Explanation:
    """Explain with the deterministic templates alone: no model, no cost."""
    return await explain(moment, facts, [])


def foundry_drafters(
    settings: FoundrySettings, credential: DefaultAzureCredential
) -> list[AgentDrafter]:
    """The Analyst on the `fast` model (minimal reasoning), then on the `fallback` model."""
    prompt = load_prompt(*PROMPT)
    return [
        foundry_analyst(
            project_endpoint=settings.project_endpoint,
            deployment=alias,
            alias=alias,
            match_data_url=settings.match_data_url,
            prompt=prompt,
            credential=credential,
            reasoning_effort=effort,
        )
        for alias, effort in MODELS
    ]


@asynccontextmanager
async def foundry_explainer(settings: FoundrySettings) -> AsyncIterator[Explainer]:
    """An explainer backed by the Analyst. Credential and MCP sessions open and close here."""
    async with AsyncExitStack() as stack:
        credential = await stack.enter_async_context(
            DefaultAzureCredential(managed_identity_client_id=settings.client_id or None)
        )
        drafters = foundry_drafters(settings, credential)
        for drafter in drafters:
            await stack.enter_async_context(drafter)

        async def explainer(moment: Moment, facts: MatchFacts) -> Explanation:
            return await explain(moment, facts, drafters)

        yield explainer
