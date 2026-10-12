"""The Analyst agent: its prompt, what it is asked, and how its answers are read."""

from dataclasses import dataclass
from typing import Any

import anyio
import pytest
from agent_framework import Agent, ChatOptions
from azure.core.credentials import AccessToken

from explain_fixtures import featured, moment
from fourth_official_contracts import Finding, Provenance
from fourth_official_explain.analyst import (
    AgentDrafter,
    DraftError,
    TokenCount,
    foundry_analyst,
    request_message,
)
from fourth_official_explain.bounds import MomentBound
from fourth_official_explain.drafts import ClaimDraft, InsightDraft
from fourth_official_explain.pipeline import LEAD_UP_EVENTS, DraftRequest, brief
from fourth_official_explain.prompts import load_prompt, parse_prompt

PROVENANCE = Provenance(agent="analyst", prompt_version="v1.0", model="fast", produced_by="model")
DRAFT = InsightDraft(
    headline="{{club:HCY}} score",
    claims=[
        ClaimDraft(
            type="stat", text="{{club:HCY}} score.", event_ids=["m42-e0001"], snapshot_ids=[]
        )
    ],
)


@dataclass
class Stub:
    value: object
    asked: list[tuple[str, ChatOptions[Any]]]

    async def __call__(self, message: str, options: ChatOptions[Any], as_of_seq: int) -> object:
        self.asked.append((message, options))
        return type("Response", (), {"value": self.value})()


def test_the_prompt_is_versioned_and_explains_references() -> None:
    prompt = load_prompt("analyst", "v1.0")

    assert (prompt.agent, prompt.version) == ("analyst", "v1.0")
    assert "{{value:<snapshotId>}}" in prompt.text
    assert "---" not in prompt.text.splitlines()[0]


@pytest.mark.parametrize(
    ("agent", "version"), [("analyst", "v9.9"), ("../etc", "v1.0"), ("analyst", "latest")]
)
def test_unknown_or_unsafe_prompts_are_refused(agent: str, version: str) -> None:
    with pytest.raises((ValueError, FileNotFoundError)):
        load_prompt(agent, version)


def test_the_request_carries_the_moment_and_any_findings() -> None:
    goal = moment("goal")
    finding = Finding(claim_id="cl-1", code="BARE_NUMBER", detail="numbers must be references")

    first = request_message(DraftRequest(moment=goal, attempt=1))
    retry = request_message(DraftRequest(moment=goal, attempt=2, feedback=(finding,)))

    assert goal.moment_id in first
    assert "Verifier" not in first
    assert "BARE_NUMBER: numbers must be references" in retry


def test_a_retry_shows_the_draft_to_fix() -> None:
    goal = moment("goal")
    finding = Finding(claim_id="cl-1", code="BARE_NUMBER", detail="numbers must be references")

    retry = request_message(
        DraftRequest(moment=goal, attempt=2, feedback=(finding,), previous=DRAFT)
    )

    assert "Your previous draft (JSON):" in retry
    assert DRAFT.model_dump_json() in retry
    assert retry.index("previous draft") < retry.index("BARE_NUMBER")


def test_the_drafter_asks_for_a_structured_draft_and_returns_it() -> None:
    stub = Stub(DRAFT, [])
    drafter = AgentDrafter(run=stub, provenance=PROVENANCE)

    draft = anyio.run(drafter.draft, DraftRequest(moment=moment("goal"), attempt=1))

    assert draft == DRAFT
    assert stub.asked[0][1] == {"response_format": InsightDraft}


def test_an_answer_without_a_structured_draft_is_an_error() -> None:
    drafter = AgentDrafter(run=Stub(None, []), provenance=PROVENANCE)

    with pytest.raises(DraftError):
        anyio.run(drafter.draft, DraftRequest(moment=moment("goal"), attempt=1))


class NoNetworkCredential:
    async def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        raise AssertionError("no token may be requested while building the agent")

    async def close(self) -> None: ...

    async def __aenter__(self) -> "NoNetworkCredential":
        return self

    async def __aexit__(self, *args: object) -> None: ...


def test_the_foundry_analyst_has_only_the_read_only_match_data_tools() -> None:
    drafter = foundry_analyst(
        project_endpoint="https://example.services.ai.azure.com/api/projects/demo",
        deployment="gpt-5-mini",
        alias="fast",
        match_data_url="http://127.0.0.1:8100/mcp",
        prompt=load_prompt("analyst", "v1.0"),
        credential=NoNetworkCredential(),
    )

    assert drafter.provenance == PROVENANCE
    assert callable(drafter.run)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("no front matter at all", "no front matter"),
        ("---\nagent: analyst\nversion: v2.0\n---\nText", "names itself"),
    ],
)
def test_a_prompt_file_must_name_itself_correctly(raw: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_prompt(raw, agent="analyst", version="v1.0")


def test_the_foundry_analyst_runs_its_agent_for_a_structured_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[dict[str, object]] = []

    async def fake_run(self: Agent, message: str, **kwargs: object) -> object:
        asked.append(kwargs)
        return type("Response", (), {"value": DRAFT})()

    monkeypatch.setattr(Agent, "run", fake_run)
    drafter = foundry_analyst(
        project_endpoint="https://example.services.ai.azure.com/api/projects/demo",
        deployment="fast",
        alias="fast",
        match_data_url="http://127.0.0.1:8100/mcp",
        prompt=load_prompt("analyst", "v1.0"),
        credential=NoNetworkCredential(),
    )

    draft = anyio.run(drafter.draft, DraftRequest(moment=moment("goal"), attempt=1))

    assert draft == DRAFT
    (call,) = asked
    assert (call["stream"], call["options"]) == (False, {"response_format": InsightDraft})
    middleware = call["middleware"]
    assert isinstance(middleware, list)
    (bound,) = middleware
    assert isinstance(bound, MomentBound)
    assert bound.as_of_seq == moment("goal").as_of_seq


def test_the_drafter_opens_and_closes_its_tool_connections_in_order() -> None:
    log: list[str] = []

    class Connection:
        def __init__(self, name: str) -> None:
            self.name = name

        async def __aenter__(self) -> "Connection":
            log.append(f"open {self.name}")
            return self

        async def __aexit__(self, *exc: object) -> None:
            log.append(f"close {self.name}")

    drafter = AgentDrafter(
        run=Stub(DRAFT, []), provenance=PROVENANCE, connections=(Connection("a"), Connection("b"))
    )

    async def use() -> None:
        async with drafter:
            log.append("draft")

    anyio.run(use)

    assert log == ["open a", "open b", "draft", "close b", "close a"]


def test_every_connection_opened_is_closed_even_when_a_later_one_fails() -> None:
    log: list[str] = []

    class Connection:
        def __init__(self, name: str, *, fails: bool = False) -> None:
            self.name, self.fails = name, fails

        async def __aenter__(self) -> "Connection":
            if self.fails:
                raise ConnectionError(self.name)
            log.append(f"open {self.name}")
            return self

        async def __aexit__(self, *exc: object) -> None:
            log.append(f"close {self.name}")

    drafter = AgentDrafter(
        run=Stub(DRAFT, []),
        provenance=PROVENANCE,
        connections=(Connection("a"), Connection("b", fails=True)),
    )

    async def use() -> None:
        async with drafter:
            log.append("never")

    with pytest.raises(ConnectionError):
        anyio.run(use)
    assert log == ["open a", "close a"]


def test_the_briefing_gives_the_score_evidence_and_lead_up() -> None:
    goal = moment("goal")
    facts, _ = featured()
    briefing = brief(goal, facts)

    message = request_message(DraftRequest(moment=goal, attempt=1, briefing=briefing))

    assert "Score at the moment: home 1, away 0" in message
    assert all(e.event_id in message for e in briefing.evidence)
    assert len(briefing.lead_up) == LEAD_UP_EVENTS
    assert all(e.seq < goal.as_of_seq for e in briefing.lead_up)


def test_leaving_a_drafter_that_was_never_entered_is_harmless() -> None:
    drafter = AgentDrafter(run=Stub(DRAFT, []), provenance=PROVENANCE)

    anyio.run(drafter.__aexit__, None, None, None)


@dataclass
class Metered:
    value: object
    usage: dict[str, int] | None

    async def __call__(self, message: str, options: ChatOptions[Any], as_of_seq: int) -> object:
        return type("Response", (), {"value": self.value, "usage_details": self.usage})()


def test_the_tokens_each_draft_spends_are_metered_under_its_model_alias() -> None:
    spent: list[TokenCount] = []
    usage = {"input_token_count": 1200, "output_token_count": 300, "total_token_count": 1500}
    drafter = AgentDrafter(run=Metered(DRAFT, usage), provenance=PROVENANCE, meter=spent.append)

    anyio.run(drafter.draft, DraftRequest(moment=moment("goal"), attempt=1))

    assert spent == [TokenCount(model=PROVENANCE.model, input=1200, output=300)]


def test_an_unusable_answer_still_counts_the_tokens_it_spent() -> None:
    spent: list[TokenCount] = []
    usage = {"input_token_count": 900, "output_token_count": 10}
    drafter = AgentDrafter(run=Metered(None, usage), provenance=PROVENANCE, meter=spent.append)

    with pytest.raises(DraftError):
        anyio.run(drafter.draft, DraftRequest(moment=moment("goal"), attempt=1))

    assert spent == [TokenCount(model=PROVENANCE.model, input=900, output=10)]


def test_an_answer_without_usage_is_metered_as_nothing() -> None:
    spent: list[TokenCount] = []
    drafter = AgentDrafter(run=Metered(DRAFT, None), provenance=PROVENANCE, meter=spent.append)

    anyio.run(drafter.draft, DraftRequest(moment=moment("goal"), attempt=1))

    assert spent == []
