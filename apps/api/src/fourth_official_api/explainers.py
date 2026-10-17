"""How the API explains moments: the Analyst on Foundry when configured, else templates alone."""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from functools import partial

from azure.identity.aio import DefaultAzureCredential

from fourth_official_api.settings import FoundrySettings
from fourth_official_contracts import Moment, TenantId, TenantPolicy
from fourth_official_explain import Explanation, explain
from fourth_official_explain.analyst import AgentDrafter
from fourth_official_explain.localize import Localizer
from fourth_official_explain.localizer import AgentLocalizer, foundry_localizer
from fourth_official_explain.production import LOCALIZER, analyst_drafters
from fourth_official_explain.prompts import load_prompt
from fourth_official_explain.warmup import Warm
from fourth_official_policy import blocked_topics_in
from fourth_official_policy.book import PolicyBook
from fourth_official_replay import Partner, Partners
from fourth_official_verifier import MatchFacts


async def template_explainer(moment: Moment, facts: MatchFacts) -> Explanation:
    """Explain with the deterministic templates alone: no model, no cost."""
    return await explain(moment, facts, [])


def foundry_drafters(
    settings: FoundrySettings, credential: DefaultAzureCredential
) -> list[AgentDrafter]:
    """The production Analyst: the `fast` model (minimal reasoning), then the `fallback` one."""
    return analyst_drafters(
        project_endpoint=settings.project_endpoint,
        match_data_url=settings.match_data_url,
        credential=credential,
    )


@dataclass(frozen=True, slots=True)
class ModelExplainer:
    """The Analyst explaining moments with its drafters in turn, and waking their deployments."""

    drafters: Sequence[AgentDrafter]

    async def __call__(self, moment: Moment, facts: MatchFacts) -> Explanation:
        return await explain(moment, facts, self.drafters)

    async def warm(self) -> None:
        """Wake every deployment the Analyst drafts on, at once."""
        await asyncio.gather(*(d.warm() for d in self.drafters if d.warm is not None))


def warming(*warms: Warm | None) -> Warm | None:
    """One warm-up that wakes every model the matchday uses, at once; None if none can be."""
    given = [w for w in warms if w is not None]
    if not given:
        return None

    async def warm() -> None:
        await asyncio.gather(*(w() for w in given))

    return warm


@asynccontextmanager
async def foundry_explainer(settings: FoundrySettings) -> AsyncIterator[ModelExplainer]:
    """An explainer backed by the Analyst. Credential and MCP sessions open and close here."""
    async with AsyncExitStack() as stack:
        credential = await stack.enter_async_context(
            DefaultAzureCredential(managed_identity_client_id=settings.client_id or None)
        )
        drafters = foundry_drafters(settings, credential)
        for drafter in drafters:
            await stack.enter_async_context(drafter)

        yield ModelExplainer(drafters=tuple(drafters))


@asynccontextmanager
async def foundry_localizer_for(settings: FoundrySettings) -> AsyncIterator[AgentLocalizer]:
    """The Localizer on the `fast` model. Its credential opens and closes here."""
    async with DefaultAzureCredential(
        managed_identity_client_id=settings.client_id or None
    ) as credential:
        yield foundry_localizer(
            project_endpoint=settings.project_endpoint,
            deployment="fast",
            alias="fast",
            prompt=load_prompt(*LOCALIZER),
            credential=credential,
            reasoning_effort="minimal",
        )


def _partner(policy: TenantPolicy) -> Partner:
    return Partner(policy=policy, blocked=partial(blocked_topics_in, policy=policy))


def partners_for(
    policies: Sequence[TenantPolicy], localizer: Localizer | None, book: PolicyBook | None = None
) -> Callable[[], Partners]:
    """A fresh set of partners for each match of each run: their policies, blocked topics and
    the Localizer (or templates alone, without one). With a policy book, each item reads its
    partner's policy as it stands then, so an edit in Policy Studio governs the next item."""

    def source(tenant_id: TenantId) -> Partner:
        assert book is not None  # noqa: S101 - only passed as the source when there is a book
        return _partner(book.current(tenant_id))

    def make() -> Partners:
        return Partners(
            [_partner(p) for p in policies],
            localizer=localizer,
            source=source if book is not None else None,
        )

    return make
