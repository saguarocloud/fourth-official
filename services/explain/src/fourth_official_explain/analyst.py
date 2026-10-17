"""The Analyst: a Microsoft Agent Framework agent on Microsoft Foundry that drafts insights,
reading the match through the Match Data MCP server."""

import json
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from agent_framework import Agent, ChatOptions, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from azure.core.credentials_async import AsyncTokenCredential

from fourth_official_contracts import Provenance
from fourth_official_explain.bounds import MomentBound
from fourth_official_explain.drafts import InsightDraft
from fourth_official_explain.metering import TokenCount, spend, usage_of
from fourth_official_explain.pipeline import DraftRequest
from fourth_official_explain.prompts import Prompt
from fourth_official_explain.warmup import Warm, warm_up

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


# Told of every call's tokens, so a caller can put a price on a run.
Meter = Callable[[TokenCount], None]


# Runs the agent on one message, with options, bounded to a moment; returns the agent's response.
RunAgent = Callable[[str, ChatOptions[Any], int], Awaitable[object]]


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
    if request.previous is not None:
        lines += ["Your previous draft (JSON):", request.previous.model_dump_json()]
    if request.feedback:
        lines.append("The Verifier refused your previous draft. Fix exactly these findings:")
        lines += [f"- {f.code}: {f.detail}" for f in request.feedback]
    return "\n".join(lines)


@dataclass(slots=True)
class AgentDrafter:
    """Drafts insights with an Agent Framework agent and its structured output.

    It is an async context manager that owns its tools' connections (the Match Data MCP session),
    so a session is opened and closed in the same task, and every connection opened is closed even
    if a later one fails.
    """

    run: RunAgent
    provenance: Provenance
    # Model-specific options, such as reasoning effort for reasoning models.
    options: Mapping[str, object] = field(default_factory=dict)
    connections: tuple[AbstractAsyncContextManager[object], ...] = ()
    # Told what each call spent, whether or not its answer was usable. A call that fails outright
    # reports nothing, so a meter can only undercount.
    meter: Meter | None = None
    # Wakes the deployment before the first moment needs it (none in tests).
    warm: Warm | None = None
    _stack: AsyncExitStack | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "AgentDrafter":
        stack = AsyncExitStack()
        try:
            for connection in self.connections:
                await stack.enter_async_context(connection)
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        return self

    async def __aexit__(self, *exc: object) -> None:
        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.__aexit__(*exc)  # type: ignore[arg-type]

    async def draft(self, request: DraftRequest) -> InsightDraft:
        options = cast("ChatOptions[Any]", {**self.options, "response_format": InsightDraft})
        response = await self.run(request_message(request), options, request.moment.as_of_seq)
        spent = usage_of(response, self.provenance.model)
        if spent is not None:
            spend(spent)
            if self.meter is not None:
                self.meter(spent)
        value = getattr(response, "value", None)
        if not isinstance(value, InsightDraft):
            raise DraftError("the model returned no structured draft")
        return value


def foundry_analyst(  # noqa: PLR0913 - the model, its tools, its prompt and its meter
    *,
    project_endpoint: str,
    deployment: str,
    alias: str,
    match_data_url: str,
    prompt: Prompt,
    credential: AsyncTokenCredential,
    reasoning_effort: Literal["minimal", "low", "medium"] | None = None,
    meter: Meter | None = None,
) -> AgentDrafter:
    """The caller owns `credential` and closes it after the drafter.

    The Analyst on a Foundry model deployment (`alias` is the configured name, such as `fast`),
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

    async def run(message: str, options: ChatOptions[Any], as_of_seq: int) -> object:
        return await agent.run(
            message, stream=False, options=options, middleware=[MomentBound(as_of_seq)]
        )

    provenance = Provenance(
        agent=prompt.agent, prompt_version=prompt.version, model=alias, produced_by="model"
    )
    options = {"reasoning": {"effort": reasoning_effort}} if reasoning_effort else {}
    return AgentDrafter(
        run=run,
        provenance=provenance,
        options=options,
        connections=(match_data,),
        meter=meter,
        warm=warm_up(client.get_response, options=options),
    )
