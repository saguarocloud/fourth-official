"""The Analyst: a Microsoft Agent Framework agent on Microsoft Foundry that drafts insights,
reading the match through the Match Data MCP server."""

import json
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from agent_framework import Agent, ChatOptions, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials_async import AsyncTokenCredential

from fourth_official_contracts import Provenance
from fourth_official_explain.drafts import InsightDraft
from fourth_official_explain.pipeline import DraftRequest
from fourth_official_explain.prompts import Prompt

MATCH_DATA_TOOLS = (
    "get_match_state",
    "get_metric",
    "compare_windows",
    "get_events",
    "get_player",
    "list_moments",
)


class DraftError(RuntimeError):
    """The model answered without a usable structured draft."""


# Runs the agent on one message with options; returns the agent's response.
RunAgent = Callable[[str, ChatOptions[Any]], Awaitable[object]]


def request_message(request: DraftRequest) -> str:
    """What the Analyst is asked: the moment as published, a briefing, and any findings to fix."""
    lines = [
        "Explain this moment.",
        "Moment (JSON):",
        json.dumps(request.moment.to_wire(), sort_keys=True),
    ]
    if request.briefing is not None:
        home, away = request.briefing.score
        lines += [
            f"Score at the moment: home {home}, away {away} (write it as {{{{score}}}}).",
            "The moment's evidence events (JSON):",
            json.dumps([e.to_wire() for e in request.briefing.evidence], sort_keys=True),
            "The events just before it (JSON):",
            json.dumps([e.to_wire() for e in request.briefing.lead_up], sort_keys=True),
        ]
    if request.feedback:
        lines.append("The Verifier refused your previous draft. Fix exactly these findings:")
        lines += [f"- {f.code}: {f.detail}" for f in request.feedback]
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AgentDrafter:
    """Drafts insights with an Agent Framework agent and its structured output."""

    run: RunAgent
    provenance: Provenance
    # Model-specific options, such as reasoning effort for reasoning models.
    options: Mapping[str, object] = field(default_factory=dict)
    # Connections the agent's tools need (the Match Data MCP session). Entered with the drafter,
    # so a session is opened and closed in the same task.
    connections: tuple[AbstractAsyncContextManager[object], ...] = ()

    async def __aenter__(self) -> "AgentDrafter":
        for connection in self.connections:
            await connection.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for connection in reversed(self.connections):
            await connection.__aexit__(None, None, None)

    async def draft(self, request: DraftRequest) -> InsightDraft:
        options = cast("ChatOptions[Any]", {**self.options, "response_format": InsightDraft})
        response = await self.run(request_message(request), options)
        value = getattr(response, "value", None)
        if not isinstance(value, InsightDraft):
            raise DraftError("the model returned no structured draft")
        return value


def foundry_analyst(
    *,
    project_endpoint: str,
    deployment: str,
    alias: str,
    match_data_url: str,
    prompt: Prompt,
    credential: AsyncTokenCredential,
    reasoning_effort: Literal["minimal", "low", "medium"] | None = None,
) -> AgentDrafter:
    """The Analyst on a Foundry model deployment (`alias` is the configured name, such as `fast`),
    with the Match Data MCP server's read-only tools and nothing else."""
    client = FoundryChatClient(
        project_endpoint=project_endpoint, model=deployment, credential=credential
    )
    match_data = MCPStreamableHTTPTool(
        name="match-data",
        url=match_data_url,
        allowed_tools=MATCH_DATA_TOOLS,
        approval_mode="never_require",
        load_prompts=False,
    )
    agent = Agent(client, prompt.text, name="analyst", tools=[match_data])

    async def run(message: str, options: ChatOptions[Any]) -> object:
        return await agent.run(message, stream=False, options=options)

    provenance = Provenance(
        agent=prompt.agent, prompt_version=prompt.version, model=alias, produced_by="model"
    )
    options = {"reasoning": {"effort": reasoning_effort}} if reasoning_effort else {}
    return AgentDrafter(run=run, provenance=provenance, options=options, connections=(match_data,))
