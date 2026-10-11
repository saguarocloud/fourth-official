"""Feed contract: what a replay publishes, each entry in order and consistent with itself."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import InsightEntry, parse_feed_entry
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
    },
    {
        "number": 2,
        "agent": "analyst",
        "model": "fast",
        "outcome": "passed",
        "findings": [],
        "error": None,
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
    ],
)
def test_incoherent_entries_are_refused(wire: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_feed_entry(wire)
