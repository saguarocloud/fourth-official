"""Correction contract: the source of truth changed after something was published."""

import pytest
from pydantic import ValidationError

from fourth_official_contracts import (
    EventAmended,
    EventVoided,
    parse_correction,
)


def _correction(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "correctionId": "c-m42-03",
        "matchId": "m42",
        "targetEventId": "m42-e0188",
        "kind": "EVENT_VOIDED",
        "reason": "VAR_OFFSIDE",
        "issuedAt": "2026-10-24T15:08:22.000Z",
        "newVersion": 2,
    }
    return {**base, **overrides}


def test_parses_a_voided_goal() -> None:
    correction = parse_correction(_correction())

    assert isinstance(correction, EventVoided)
    assert correction.target_event_id == "m42-e0188"


def test_parses_a_reassigned_scorer() -> None:
    correction = parse_correction(
        _correction(
            kind="EVENT_AMENDED",
            reason="ACCREDITATION_PANEL",
            changes={"scorerId": "HCY-11"},
        )
    )

    assert isinstance(correction, EventAmended)
    assert correction.changes.scorer_id == "HCY-11"


def test_round_trips_through_the_wire_format() -> None:
    raw = _correction(
        kind="EVENT_AMENDED", reason="ACCREDITATION_PANEL", changes={"scorerId": "HCY-11"}
    )

    assert parse_correction(raw).to_wire() == raw


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("correctionId", "c3"),
        ("correctionId", "c-m41-03"),  # issued for another match
        ("correctionId", "c-m42-3"),
        ("targetEventId", "m41-e0188"),  # another match's event
        ("newVersion", 1),  # a correction always creates a new version
        ("reason", "BECAUSE"),
        ("issuedAt", "2026-10-24T15:08:22"),
        ("kind", "EVENT_RENAMED"),
    ],
)
def test_refuses_malformed_corrections(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        parse_correction(_correction(**{field: value}))


def test_refuses_an_amendment_that_changes_nothing() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        parse_correction(_correction(kind="EVENT_AMENDED", changes={}))


def test_refuses_a_voiding_that_carries_changes() -> None:
    with pytest.raises(ValidationError):
        parse_correction(_correction(changes={"scorerId": "HCY-11"}))
