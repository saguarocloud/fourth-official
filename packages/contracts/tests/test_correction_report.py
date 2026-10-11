"""What a correction did to everything already published: each partner item it touched, what was
done to it, and how long it took. It replays the impact graph for the Corrections Center."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import CorrectionReportEntry, parse_feed_entry
from test_tenants import TENANT_ITEM, changed

ITEM_V1 = "it-rheinblick-sport-in-m42-goal-HCY-s0287-a1-v1"
ITEM_V2 = "it-rheinblick-sport-in-m42-goal-HCY-s0287-a1-v2"

REPORT: dict[str, Any] = {
    "kind": "correction_report",
    "entrySeq": 90,
    "matchId": "m42",
    "correctionId": "c-m42-02",
    "targetEventId": "m42-e0287",
    "startedAt": "2026-10-11T15:00:00.000Z",
    "elapsedMs": 412,
    "insightIds": ["in-m42-goal-HCY-s0287-a1"],
    "actions": [
        {
            "tenantId": "rheinblick-sport",
            "locale": "de-DE",
            "insightId": "in-m42-goal-HCY-s0287-a1",
            "itemId": ITEM_V1,
            "was": "on_air",
            "action": "amended",
            "newItemId": ITEM_V2,
        },
        {
            "tenantId": "tribuna-austral",
            "locale": "es-MX",
            "insightId": "in-m42-goal-HCY-s0287-a1",
            "itemId": "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1",
            "was": "pending_approval",
            "action": "retracted",
            "newItemId": None,
        },
    ],
}


def test_a_report_is_a_feed_entry() -> None:
    entry = parse_feed_entry(REPORT)

    assert isinstance(entry, CorrectionReportEntry)
    assert entry.elapsed_ms == 412
    assert [a.action for a in entry.actions] == ["amended", "retracted"]
    assert entry.to_wire() == REPORT


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("correctionId",), "c-m43-02"),  # another match's correction
        (("targetEventId",), "m43-e0287"),  # another match's event
        (("elapsedMs",), -1),
        (("actions", 0, "newItemId"), None),  # an amendment names its new version
        (("actions", 1, "newItemId"), ITEM_V2),  # a retraction has none
        (("actions", 0, "newItemId"), "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v2"),
        (("actions", 0, "newItemId"), ITEM_V1),  # the new version is a later one
        (("actions", 0, "itemId"), "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1"),
        (("actions", 0, "action"), "deleted"),
        (("actions", 0, "locale"), "es-MX"),  # the partner's own language
        # The next version, not any later one.
        (("actions", 0, "newItemId"), "it-rheinblick-sport-in-m42-goal-HCY-s0287-a1-v3"),
        # A held item can only be pulled: it was never on air to replace.
        (("actions", 1, "action"), "amended"),
        # Every action is about an insight the report lists.
        (("insightIds",), []),
        # The item belongs to exactly this insight, not one whose id merely starts the same.
        (("actions", 0, "insightId"), "in-m42-goal-HCY-s0287-a"),
    ],
)
def test_an_inconsistent_report_is_refused(path: tuple[str | int, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        parse_feed_entry(changed(REPORT, path, value))  # type: ignore[arg-type]


def test_an_item_can_be_retracted_or_amended_after_a_correction() -> None:
    for state in ("retracted", "amended"):
        assert parse_feed_entry(changed(TENANT_ITEM, ("state",), state)).state == state  # type: ignore[union-attr]


def test_an_item_is_acted_on_once_per_report() -> None:
    twice = changed(REPORT, ("actions",), [REPORT["actions"][0], REPORT["actions"][0]])

    with pytest.raises(ValidationError):
        parse_feed_entry(twice)
