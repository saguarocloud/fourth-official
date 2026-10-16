"""The operations report: what the platform measured, as counts and durations, never rates."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import OperationsReport, parse_operations_report


def spread(count: int = 2, p50: int | None = 3000, p95: int | None = 6000) -> dict[str, Any]:
    return {"count": count, "p50Ms": p50, "p95Ms": p95}


def partner(**overrides: object) -> dict[str, Any]:
    return {
        "tenantId": "rheinblick-sport",
        "items": 3,
        "held": 1,
        "onAir": spread(),
        "withinTarget": {"hit": 2, "of": 2},
        **overrides,
    }


def match(**overrides: object) -> dict[str, Any]:
    return {
        "matchId": "m42",
        "state": "finished",
        "runMs": 600_000,
        "eventsPlayed": 1400,
        "moments": 12,
        "explain": spread(12, 2500, 9000),
        "firstPass": {"hit": 9, "of": 12},
        "fallbacks": {"hit": 1, "of": 12},
        "modelDrafts": {"hit": 11, "of": 15},
        "modelErrors": 1,
        "corrections": spread(1, 40, 40),
        "correctedItems": 6,
        "partners": [partner()],
        **overrides,
    }


def report(**overrides: object) -> dict[str, Any]:
    return {
        "generatedAt": "2026-10-16T09:00:00Z",
        "objectives": [
            {"key": "on_air_p50", "targetMs": 4000, "measuredMs": 3000},
            {"key": "on_air_p95", "targetMs": 8000, "measuredMs": 6000},
            {"key": "correction_p95", "targetMs": 10000, "measuredMs": 40},
        ],
        "budget": {"withinPercent": 95, "targetMs": 8000, "late": 0, "of": 2},
        "onAir": spread(),
        "matches": [match()],
        **overrides,
    }


def test_a_report_round_trips_on_the_wire() -> None:
    parsed = parse_operations_report(report())

    assert isinstance(parsed, OperationsReport)
    assert parse_operations_report(parsed.to_wire()) == parsed


def test_nothing_measured_has_no_percentiles_and_something_measured_has_both() -> None:
    parse_operations_report(report(onAir=spread(0, None, None)))
    with pytest.raises(ValidationError, match="percentiles"):
        parse_operations_report(report(onAir=spread(0, 10, 10)))
    with pytest.raises(ValidationError, match="percentiles"):
        parse_operations_report(report(onAir=spread(3, None, 10)))


def test_the_median_is_never_above_the_95th_percentile() -> None:
    with pytest.raises(ValidationError, match="median"):
        parse_operations_report(report(onAir=spread(3, 9000, 8000)))


def test_a_partner_holds_no_more_items_than_it_published() -> None:
    with pytest.raises(ValidationError, match="held"):
        parse_operations_report(report(matches=[match(partners=[partner(held=4)])]))


def test_each_objective_is_reported_once() -> None:
    twice = {"key": "on_air_p50", "targetMs": 4000, "measuredMs": None}
    with pytest.raises(ValidationError, match="once"):
        parse_operations_report(report(objectives=[twice, twice]))


def test_late_items_are_items_measured() -> None:
    with pytest.raises(ValidationError, match="late"):
        parse_operations_report(
            report(budget={"withinPercent": 95, "targetMs": 8000, "late": 3, "of": 2})
        )


def test_a_match_is_reported_once() -> None:
    with pytest.raises(ValidationError, match="once"):
        parse_operations_report(report(matches=[match(), match()]))
