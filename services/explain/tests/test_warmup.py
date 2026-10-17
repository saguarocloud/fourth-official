"""Warming a model deployment: one tiny request through the client the agent uses, bounded."""

import asyncio
from typing import Any

import anyio
import pytest
from agent_framework import ChatResponse, Message
from agent_framework.foundry import FoundryChatClient

from fourth_official_explain.analyst import foundry_analyst
from fourth_official_explain.localizer import foundry_localizer
from fourth_official_explain.prompts import load_prompt
from fourth_official_explain.warmup import warm_up
from test_analyst import NoNetworkCredential

ENDPOINT = "https://example.services.ai.azure.com/api/projects/demo"


class Recording:
    def __init__(self, delay: float = 0.0) -> None:
        self.calls: list[dict[str, Any]] = []
        self.delay = delay

    async def get_response(self, messages: list[Message], **kwargs: Any) -> ChatResponse[Any]:  # noqa: ANN401
        self.calls.append({"messages": messages, **kwargs})
        await asyncio.sleep(self.delay)
        return ChatResponse(messages=[Message("assistant", ["OK"])])


def test_a_warm_up_is_one_short_request_with_the_model_s_options() -> None:
    client = Recording()

    anyio.run(warm_up(client.get_response, options={"reasoning": {"effort": "minimal"}}))

    (call,) = client.calls
    assert call["messages"][0].text == "Reply with OK."
    assert call["options"]["reasoning"] == {"effort": "minimal"}
    assert call["options"]["max_tokens"] <= 64


def test_a_warm_up_that_hangs_is_given_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fourth_official_explain.warmup.WARM_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(TimeoutError):
        anyio.run(warm_up(Recording(delay=1.0).get_response, options={}))


def test_the_analyst_and_the_localizer_warm_their_own_deployments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warmed: list[str] = []

    async def fake(self: FoundryChatClient, messages: object, **kwargs: object) -> object:
        warmed.append(str(self.model))
        return ChatResponse(messages=[Message("assistant", ["OK"])])

    monkeypatch.setattr(FoundryChatClient, "get_response", fake)
    analyst = foundry_analyst(
        project_endpoint=ENDPOINT,
        deployment="fallback",
        alias="fallback",
        match_data_url="http://127.0.0.1:8100/mcp",
        prompt=load_prompt("analyst", "v1.2"),
        credential=NoNetworkCredential(),
    )
    localizer = foundry_localizer(
        project_endpoint=ENDPOINT,
        deployment="fast",
        alias="fast",
        prompt=load_prompt("localizer", "v1.0"),
        credential=NoNetworkCredential(),
    )

    assert analyst.warm is not None
    assert localizer.warm is not None
    anyio.run(analyst.warm)
    anyio.run(localizer.warm)

    assert warmed == ["fallback", "fast"]
