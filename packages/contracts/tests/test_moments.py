"""Moment contract: something worth explaining, found by deterministic rules, with its evidence."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import (
    Moment,
    SnapshotIdParts,
    moment_id_for,
    parse_moment,
    parse_moment_json,
    snapshot_id_parts,
)

BEFORE = "ms-m42-pressing_intensity-NGT-15m-s1500-v1"
AFTER = "ms-m42-pressing_intensity-NGT-5m-s1690-v1"
COLLAPSE: dict[str, Any] = {
    "momentId": "mo-m42-pressing_collapse-NGT-s1690",
    "matchId": "m42",
    "kind": "pressing_collapse",
    "club": "NGT",
    "asOfSeq": 1690,
    "clock": {"period": 2, "minute": 65, "second": 4},
    "eventIds": [],
    "metricSnapshotIds": [BEFORE, AFTER],
    "shifts": [
        {
            "metric": "pressing_intensity",
            "before": 3.4,
            "after": 0.8,
            "beforeSnapshotId": BEFORE,
            "afterSnapshotId": AFTER,
        }
    ],
}
GOAL: dict[str, Any] = {
    "momentId": "mo-m42-goal-HCY-s0287",
    "matchId": "m42",
    "kind": "goal",
    "club": "HCY",
    "asOfSeq": 287,
    "clock": {"period": 1, "minute": 12, "second": 26},
    "eventIds": ["m42-e0286", "m42-e0287"],
    "metricSnapshotIds": [],
    "shifts": [],
}


def shifted(**changes: object) -> dict[str, Any]:
    return COLLAPSE | {"shifts": [COLLAPSE["shifts"][0] | changes]}


def test_moments_round_trip_the_wire() -> None:
    for wire in (COLLAPSE, GOAL):
        moment = parse_moment(wire)
        assert isinstance(moment, Moment)
        assert moment.to_wire() == wire
        assert parse_moment_json(moment.model_dump_json()) == moment


def test_the_id_names_the_match_kind_club_and_moment() -> None:
    assert (
        moment_id_for("m42", kind="pressing_collapse", club="NGT", as_of_seq=1690)
        == COLLAPSE["momentId"]
    )


@pytest.mark.parametrize(
    ("wire", "message"),
    [
        (COLLAPSE | {"momentId": "mo-m42-pressing_collapse-NGT-s1691"}, "does not name"),
        (GOAL | {"eventIds": []}, "needs the events"),
        (GOAL | {"eventIds": ["m42-e0287", "m42-e0286"]}, "match order"),
        (GOAL | {"eventIds": ["m42-e0286", "m42-e0286"]}, "match order"),
        (GOAL | {"eventIds": ["m7-e0286"]}, "another match"),
        (COLLAPSE | {"shifts": []}, "needs the metric shift"),
        (COLLAPSE | {"metricSnapshotIds": [BEFORE]}, "cited"),
        (COLLAPSE | {"metricSnapshotIds": [BEFORE, AFTER, BEFORE]}, "unique"),
        (
            COLLAPSE | {"metricSnapshotIds": [BEFORE, "ms-m7-xg-NGT-5m-s0001-v1", AFTER]},
            "another match",
        ),
        (shifted(afterSnapshotId=BEFORE), "differ"),
        (shifted(metric="xg"), "measures"),
        (shifted(after=float("nan")), "finite"),
        (
            COLLAPSE
            | {
                "metricSnapshotIds": [BEFORE, "ms-m42-pressing_intensity-HCY-5m-s1690-v1"],
                "shifts": [
                    COLLAPSE["shifts"][0]
                    | {"afterSnapshotId": "ms-m42-pressing_intensity-HCY-5m-s1690-v1"}
                ],
            },
            "about",
        ),
    ],
)
def test_incoherent_moments_are_refused(wire: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_moment(wire)


def test_moments_are_immutable() -> None:
    moment = parse_moment(GOAL)

    with pytest.raises(ValidationError):
        moment.club = "NGT"  # type: ignore[misc]


def test_snapshot_ids_read_back_into_their_parts() -> None:
    assert snapshot_id_parts(BEFORE) == SnapshotIdParts(
        "m42", "pressing_intensity", "NGT", "15m", 1500, 1
    )
    with pytest.raises(ValueError, match="not a snapshot ID"):
        snapshot_id_parts("ms-m42-xg")
