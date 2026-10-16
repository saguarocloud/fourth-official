"""Feed contract: what a replay publishes, each entry in order and consistent with itself."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import AttemptRecord, InsightEntry, parse_feed_entry
from test_insights import INSIGHT
from test_moments import GOAL

PASSED = {"insightId": INSIGHT["insightId"], "matchId": "m42", "passed": True, "findings": []}
ATTEMPTS = [
    {
        "number": 1,
        "agent": "analyst",
        "model": "fast",
        "outcome": "failed",
        "findings": ["BARE_NUMBER"],
        "error": None,
        "inputTokens": 1400,
        "outputTokens": 260,
    },
    {
        "number": 2,
        "agent": "analyst",
        "model": "fast",
        "outcome": "passed",
        "findings": [],
        "error": None,
        "inputTokens": 1650,
        "outputTokens": 240,
    },
]
INSIGHT_ENTRY: dict[str, Any] = {
    "kind": "insight",
    "entrySeq": 7,
    "matchId": "m42",
    "insight": INSIGHT,
    "verdict": PASSED,
    "rendered": {"headline": "Northgate FC have stopped pressing", "claims": ["One.", "Two."]},
    "attempts": ATTEMPTS,
}
ENTRIES: list[dict[str, Any]] = [
    {
        "kind": "clock",
        "entrySeq": 1,
        "matchId": "m42",
        "asOfSeq": 287,
        "clock": {"period": 1, "minute": 12, "second": 26},
        "score": {"home": 1, "away": 0},
    },
    {"kind": "moment", "entrySeq": 2, "matchId": "m42", "moment": GOAL},
    INSIGHT_ENTRY,
    {
        "kind": "correction",
        "entrySeq": 8,
        "matchId": "m42",
        "correction": {
            "correctionId": "c-m42-01",
            "matchId": "m42",
            "targetEventId": "m42-e0287",
            "kind": "EVENT_VOIDED",
            "reason": "VAR_OFFSIDE",
            "issuedAt": "2026-10-24T15:27:39.000Z",
            "newVersion": 2,
        },
        "summary": "Harbour City goal at 67' ruled out for offside",
        "outText": "2-0",
        "inText": "1-0",
    },
]


@pytest.mark.parametrize("wire", ENTRIES)
def test_every_kind_of_entry_round_trips_the_wire(wire: dict[str, Any]) -> None:
    assert parse_feed_entry(wire).to_wire() == wire


def test_an_insight_entry_is_typed() -> None:
    assert isinstance(parse_feed_entry(INSIGHT_ENTRY), InsightEntry)


@pytest.mark.parametrize(
    ("wire", "message"),
    [
        (
            INSIGHT_ENTRY
            | {
                "verdict": PASSED
                | {
                    "passed": False,
                    "findings": [{"claimId": None, "code": "BARE_NUMBER", "detail": "x"}],
                }
            },
            "passing verdict",
        ),
        (
            INSIGHT_ENTRY | {"verdict": PASSED | {"insightId": "in-m42-goal-HCY-s0287-a1"}},
            "passing verdict",
        ),
        (INSIGHT_ENTRY | {"rendered": {"headline": "x", "claims": ["only one"]}}, "every claim"),
        (INSIGHT_ENTRY | {"attempts": ATTEMPTS[:1]}, "last attempt"),
        (INSIGHT_ENTRY | {"matchId": "m7"}, "another match"),
        (ENTRIES[1] | {"matchId": "m7"}, "another match"),
        (ENTRIES[3] | {"matchId": "m7"}, "another match"),
        (INSIGHT_ENTRY | {"attempts": [ATTEMPTS[1] | {"error": "not a class name!"}]}, "error"),
        (INSIGHT_ENTRY | {"entrySeq": 0}, "entrySeq"),
        (ENTRIES[3] | {"inText": "no goal"}, "inText"),
        (ENTRIES[3] | {"outText": "WAY TOO LONG FOR A BOARD"}, "outText"),
    ],
)
def test_incoherent_entries_are_refused(wire: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_feed_entry(wire)


def test_an_attempt_records_the_tokens_its_model_spent_and_none_by_default() -> None:
    spent = AttemptRecord.model_validate(
        {
            "number": 1,
            "agent": "analyst",
            "model": "fast",
            "outcome": "passed",
            "findings": [],
            "error": None,
            "inputTokens": 1200,
            "outputTokens": 300,
        }
    )
    assert (spent.input_tokens, spent.output_tokens) == (1200, 300)
    assert spent.to_wire()["inputTokens"] == 1200

    recorded_before = AttemptRecord.model_validate(
        {
            "number": 1,
            "agent": "template",
            "model": "none",
            "outcome": "passed",
            "findings": [],
            "error": None,
        }
    )
    assert (recorded_before.input_tokens, recorded_before.output_tokens) == (0, 0)

    with pytest.raises(ValidationError):
        AttemptRecord.model_validate({**spent.to_wire(), "inputTokens": -1})
