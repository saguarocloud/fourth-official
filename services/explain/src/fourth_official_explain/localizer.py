"""The Localizer: a Microsoft Agent Framework agent on Microsoft Foundry that rewrites a verified
insight in a partner's language and voice. It has no tools: everything it may say is in the
canonical insight it is given, and its structured output is words only."""

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from agent_framework import Agent, ChatOptions
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials_async import AsyncTokenCredential

from fourth_official_contracts import Provenance
from fourth_official_explain.analyst import DraftError
from fourth_official_explain.localize import LocalizationRequest, LocalizedDraft
from fourth_official_explain.metering import spend, usage_of
from fourth_official_explain.prompts import Prompt
from fourth_official_explain.warmup import Warm, warm_up

# Runs the agent on one message with options; returns the agent's response.
RunAgent = Callable[[str, ChatOptions[Any]], Awaitable[object]]


def localization_message(request: LocalizationRequest) -> str:
    """What the Localizer is asked: the partner, the canonical insight, and any findings to fix."""
    policy, canonical = request.policy, request.canonical
    partner = {
        "locale": policy.locale,
        "tone": list(policy.tone),
        "preferTerms": list(policy.prefer_terms),
        "avoidTerms": list(policy.avoid_terms),
    }
    insight = {
        "headline": canonical.headline,
        "claims": [{"claimId": c.claim_id, "text": c.text} for c in canonical.claims],
    }
    lines = [
        "Rewrite this insight for the partner.",
        "Partner (JSON):",
        json.dumps(partner, ensure_ascii=False),
        "Canonical insight (JSON):",
        json.dumps(insight, ensure_ascii=False),
    ]
    if request.previous is not None:
        lines += ["Your previous draft (JSON):", request.previous.model_dump_json()]
    if request.feedback:
        lines.append("The Verifier refused your previous draft. Fix exactly these findings:")
        # One line each: a finding may quote the draft, and a draft is model output.
        lines += [f"- {f.code}: {' '.join(f.detail.split())}" for f in request.feedback]
    return "\n".join(lines)


@dataclass(slots=True)
class AgentLocalizer:
    """Localises with an Agent Framework agent and its structured output."""

    run: RunAgent
    provenance: Provenance
    # Model-specific options, such as reasoning effort for reasoning models.
    options: Mapping[str, object] = field(default_factory=dict)
    # Wakes the deployment before the first item needs it (none in tests).
    warm: Warm | None = None

    async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
        options = cast("ChatOptions[Any]", {**self.options, "response_format": LocalizedDraft})
        response = await self.run(localization_message(request), options)
        spent = usage_of(response, self.provenance.model)
        if spent is not None:
            spend(spent)
        value = getattr(response, "value", None)
        if not isinstance(value, LocalizedDraft):
            raise DraftError("the model returned no structured draft")
        return value


def foundry_localizer(
    *,
    project_endpoint: str,
    deployment: str,
    alias: str,
    prompt: Prompt,
    credential: AsyncTokenCredential,
    reasoning_effort: Literal["minimal", "low", "medium"] | None = None,
) -> AgentLocalizer:
    """The Localizer on a Foundry model deployment (`alias` is the configured name, such as
    `fast`). The caller owns `credential` and closes it after the localizer."""
    client = FoundryChatClient(
        project_endpoint=project_endpoint, model=deployment, credential=credential
    )
    agent = Agent(client, prompt.text, name="localizer")

    async def run(message: str, options: ChatOptions[Any]) -> object:
        return await agent.run(message, stream=False, options=options)

    provenance = Provenance(
        agent=prompt.agent, prompt_version=prompt.version, model=alias, produced_by="model"
    )
    options = {"reasoning": {"effort": reasoning_effort}} if reasoning_effort else {}
    return AgentLocalizer(
        run=run,
        provenance=provenance,
        options=options,
        warm=warm_up(client.get_response, options=options),
    )
