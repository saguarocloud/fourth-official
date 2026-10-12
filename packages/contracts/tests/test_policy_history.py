"""A partner's policy history: every version, and who changed what, when and why."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import parse_policy_history, parse_tenant_policy

BASE: dict[str, Any] = {
    "tenantId": "rheinblick-sport",
    "version": 1,
    "displayName": "Rheinblick Sport",
    "locale": "de-DE",
    "tone": ["formal", "precise"],
    "preferTerms": ["Pressing"],
    "avoidTerms": ["Wahnsinn"],
    "blockedTopics": ["betting"],
    "approvalRequired": ["recap"],
    "disclosureMode": "eu-strict",
    "latencyBudgetMs": 8000,
    "maxItemsPerMinute": 4,
    "templates": ["lower_third", "stat_card", "correction_strap", "score_bug"],
    "correctionBehaviour": "auto-amend",
    "dutyEditor": "L. Vogt",
}


def change(version: int, **fields: object) -> dict[str, Any]:
    return {
        "tenantId": "rheinblick-sport",
        "version": version,
        "action": "bundled" if version == 1 else "edited",
        "editor": "L. Vogt",
        "changedAt": f"2026-10-12T0{version}:00:00.000Z",
        "reason": "Shipped with the release" if version == 1 else "Hold insights for review",
        "fields": [] if version == 1 else ["approvalRequired"],
    } | fields


def history(**fields: object) -> dict[str, Any]:
    second = BASE | {"version": 2, "approvalRequired": ["recap", "insight"]}
    return {
        "tenantId": "rheinblick-sport",
        "versions": [BASE, second],
        "changes": [change(1), change(2)],
    } | fields


def test_a_history_reads_back_as_it_was_written() -> None:
    read = parse_policy_history(history())

    assert read.current.version == 2
    assert read.current.approval_required == ("recap", "insight")
    assert read.changes[-1].fields == ("approvalRequired",)
    assert parse_policy_history(read.to_wire()) == read


def test_the_current_policy_is_a_policy() -> None:
    assert parse_tenant_policy(history()["versions"][1]).version == 2


@pytest.mark.parametrize(
    ("why", "fields"),
    [
        ("a version skipped", {"versions": [BASE, BASE | {"version": 3}]}),
        (
            "another partner's policy",
            {
                "versions": [
                    BASE,
                    BASE | {"version": 2, "tenantId": "northlight-sport", "locale": "en-GB"},
                ]
            },
        ),
        ("a version without its change", {"changes": [change(1)]}),
        ("a change of another version", {"changes": [change(1), change(3)]}),
        ("a reason over two lines", {"changes": [change(1), change(2, reason="a\nb")]}),
        ("an unknown field changed", {"changes": [change(1), change(2, fields=["secret"])]}),
        ("no versions", {"versions": [], "changes": []}),
    ],
)
def test_an_inconsistent_history_is_refused(why: str, fields: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        parse_policy_history(history(**fields))
