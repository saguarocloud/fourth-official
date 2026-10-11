"""The Localizer agent: its prompt, what it is asked, and how its answers are read."""

from typing import Any

import anyio
import pytest
from agent_framework import Agent

from fourth_official_contracts import Finding, Provenance
from fourth_official_explain.analyst import DraftError
from fourth_official_explain.localize import LocalizationRequest, LocalizedDraft
from fourth_official_explain.localizer import foundry_localizer, localization_message
from fourth_official_explain.prompts import load_prompt
from test_analyst import NoNetworkCredential
from test_localize import CANONICAL, GOOD, TRIBUNA

ENDPOINT = "https://example.services.ai.azure.com/api/projects/demo"


def test_the_prompt_is_versioned_and_keeps_the_facts() -> None:
    prompt = load_prompt("localizer", "v1.0")

    assert (prompt.agent, prompt.version) == ("localizer", "v1.0")
    assert "{{club:HCY}}" in prompt.text
    assert "same order" in prompt.text


def test_the_request_carries_the_canonical_insight_and_the_partner_s_voice() -> None:
    message = localization_message(LocalizationRequest(CANONICAL, TRIBUNA, attempt=1))

    assert "es-MX" in message
    assert "energetic" in message
    assert CANONICAL.claims[0].text in message
    assert '"claimId": "cl-1"' in message
    assert "previous draft" not in message


def test_a_retry_shows_the_draft_and_the_findings() -> None:
    finding = Finding(claim_id="cl-1", code="REFERENCES_CHANGED", detail="keep the references")

    message = localization_message(
        LocalizationRequest(CANONICAL, TRIBUNA, attempt=2, feedback=(finding,), previous=GOOD)
    )

    assert "Your previous draft (JSON):" in message
    assert GOOD.model_dump_json() in message
    assert "REFERENCES_CHANGED: keep the references" in message


def test_the_foundry_localizer_asks_its_agent_for_words_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[dict[str, Any]] = []

    async def fake_run(self: Agent, message: str, **kwargs: object) -> object:
        asked.append({"tools": self.default_options.get("tools"), **kwargs})
        return type("Response", (), {"value": GOOD})()

    monkeypatch.setattr(Agent, "run", fake_run)
    localizer = foundry_localizer(
        project_endpoint=ENDPOINT,
        deployment="fast",
        alias="fast",
        prompt=load_prompt("localizer", "v1.0"),
        credential=NoNetworkCredential(),
        reasoning_effort="minimal",
    )

    draft = anyio.run(localizer.draft, LocalizationRequest(CANONICAL, TRIBUNA, attempt=1))

    assert draft == GOOD
    assert localizer.provenance == Provenance(
        agent="localizer", prompt_version="v1.0", model="fast", produced_by="model"
    )
    (call,) = asked
    assert call["options"] == {
        "reasoning": {"effort": "minimal"},
        "response_format": LocalizedDraft,
    }
    assert not call["tools"]


def test_an_answer_without_a_structured_draft_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(self: Agent, message: str, **kwargs: object) -> object:
        return type("Response", (), {"value": None})()

    monkeypatch.setattr(Agent, "run", fake_run)
    localizer = foundry_localizer(
        project_endpoint=ENDPOINT,
        deployment="fast",
        alias="fast",
        prompt=load_prompt("localizer", "v1.0"),
        credential=NoNetworkCredential(),
    )

    with pytest.raises(DraftError):
        anyio.run(localizer.draft, LocalizationRequest(CANONICAL, TRIBUNA, attempt=1))
