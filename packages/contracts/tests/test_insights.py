"""Insight contract: an explanation of a moment as typed claims, each with its evidence.

Claims never carry raw numbers or names: they reference them with markup (`{{value:ms-…}}`,
`{{player:HCY-09}}`, `{{club:HCY}}`, `{{minute:61}}`, `{{score}}`), and code renders the facts.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import (
    Insight,
    claim_references,
    insight_id_for,
    parse_insight,
    parse_insight_json,
)

SNAP = "ms-m42-pressing_intensity-NGT-5m-s1690-v1"
BASE = "ms-m42-pressing_intensity-NGT-15m-s1500-v1"
INSIGHT: dict[str, Any] = {
    "insightId": "in-m42-pressing_collapse-NGT-s1690-a1",
    "matchId": "m42",
    "momentId": "mo-m42-pressing_collapse-NGT-s1690",
    "asOfSeq": 1690,
    "locale": "en",
    "headline": "{{club:NGT}} have stopped pressing",
    "claims": [
        {
            "claimId": "cl-1",
            "type": "comparison",
            "text": "{{club:NGT}} now press {{value:" + SNAP + "}} times per opponent touch, "
            "down from {{value:" + BASE + "}}.",
            "evidence": {"eventIds": [], "metricSnapshotIds": [BASE, SNAP]},
        },
        {
            "claimId": "cl-2",
            "type": "causal",
            "text": "Since the {{minute:61}} mark {{player:HCY-08}} has had time on the ball.",
            "evidence": {"eventIds": ["m42-e1601", "m42-e1650"], "metricSnapshotIds": []},
        },
    ],
    "provenance": {
        "agent": "analyst",
        "promptVersion": "v1.3",
        "model": "fast",
        "producedBy": "model",
    },
}


def claim(index: int, **changes: object) -> dict[str, Any]:
    claims = [dict(c) for c in INSIGHT["claims"]]
    claims[index] = claims[index] | changes
    return INSIGHT | {"claims": claims}


def test_insights_round_trip_the_wire() -> None:
    insight = parse_insight(INSIGHT)

    assert isinstance(insight, Insight)
    assert insight.to_wire() == INSIGHT
    assert parse_insight_json(insight.model_dump_json()) == insight


def test_the_id_names_the_moment_and_the_attempt() -> None:
    assert insight_id_for("mo-m42-pressing_collapse-NGT-s1690", attempt=1) == INSIGHT["insightId"]


def test_markup_is_read_back_as_references() -> None:
    text = "{{club:NGT}} press {{value:" + SNAP + "}} since {{minute:61}}; it is {{score}}."

    assert claim_references(text) == (
        ("club", "NGT"),
        ("value", SNAP),
        ("minute", "61"),
        ("score", ""),
    )


@pytest.mark.parametrize(
    ("wire", "message"),
    [
        (INSIGHT | {"insightId": "in-m42-goal-HCY-s0287-a1"}, "does not name"),
        (
            INSIGHT | {"momentId": "mo-m7-goal-HCY-s0287", "insightId": "in-m7-goal-HCY-s0287-a1"},
            "another match",
        ),
        (INSIGHT | {"claims": []}, "at least 1"),
        (claim(0, evidence={"eventIds": [], "metricSnapshotIds": []}), "evidence"),
        (claim(1, claimId="cl-1"), "unique"),
        (
            claim(0, text="{{value:" + SNAP + "}} and {{value:ms-m42-xg-NGT-5m-s1690-v1}}"),
            "not cited",
        ),
        (claim(0, text="{{colour:red}} shirts"), "markup"),
        (claim(0, text="{{player:Smith}} scored"), "markup"),
        (claim(0, text="{{minute:61"), "markup"),
        (claim(1, evidence={"eventIds": ["m7-e0001"], "metricSnapshotIds": []}), "another match"),
        (claim(0, text="x" * 281), "at most 280"),
        (claim(0, text="two\nlines"), "single line"),
        (
            INSIGHT | {"provenance": INSIGHT["provenance"] | {"promptVersion": "latest"}},
            "promptVersion",
        ),
        (INSIGHT | {"locale": "es-MX"}, "locale"),
        (claim(1, text="Since {{minute:131}}, nothing."), "beyond the match"),
        (INSIGHT | {"headline": "{{value:ms-m42-xg-NGT-5m-s1690-v1}}"}, "not cited by any claim"),
        (INSIGHT | {"headline": "Two\nlines"}, "single line"),
    ],
)
def test_incoherent_insights_are_refused(wire: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_insight(wire)
