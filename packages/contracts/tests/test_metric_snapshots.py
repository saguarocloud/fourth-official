"""Metric snapshot contract: a computed number with the exact evidence it came from."""

import pytest
from pydantic import ValidationError

from fourth_official_contracts import MetricSnapshot, parse_metric_snapshot

SNAPSHOT = {
    "snapshotId": "ms-m42-possession-HCY-5m-s0187-v1",
    "matchId": "m42",
    "metric": "possession",
    "scope": "HCY",
    "window": "5m",
    "asOf": {"period": 2, "minute": 67, "second": 12},
    "asOfSeq": 187,
    "value": 0.5833,
    "inputs": ["m42-e0150", "m42-e0151"],
    "version": 1,
    "supersedes": None,
}


def test_parses_a_snapshot_and_round_trips() -> None:
    snapshot = parse_metric_snapshot(SNAPSHOT)

    assert isinstance(snapshot, MetricSnapshot)
    assert snapshot.to_wire() == SNAPSHOT


def test_a_metric_can_be_undefined() -> None:
    # PPDA has no value when the pressing team made no defensive actions.
    undefined = SNAPSHOT | {
        "metric": "ppda",
        "value": None,
        "snapshotId": "ms-m42-ppda-HCY-5m-s0187-v1",
    }

    assert parse_metric_snapshot(undefined).value is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("metric", "vibes"),
        ("scope", "hcy"),
        ("window", "7m"),
        ("inputs", ["m41-e0150"]),  # evidence from another match
        ("version", 0),
        ("snapshotId", "snapshot-1"),
    ],
)
def test_refuses_malformed_snapshots(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        parse_metric_snapshot(SNAPSHOT | {field: value})


def test_a_restated_snapshot_names_the_one_it_supersedes() -> None:
    restated = parse_metric_snapshot(
        SNAPSHOT
        | {
            "snapshotId": "ms-m42-possession-HCY-5m-s0187-v2",
            "version": 2,
            "supersedes": "ms-m42-possession-HCY-5m-s0187-v1",
        }
    )

    assert restated.supersedes == "ms-m42-possession-HCY-5m-s0187-v1"


def test_a_first_version_supersedes_nothing() -> None:
    with pytest.raises(ValidationError, match="supersede"):
        parse_metric_snapshot(SNAPSHOT | {"supersedes": "ms-m42-possession-HCY-5m-s0187-v0"})


@pytest.mark.parametrize(
    "overrides",
    [
        {"metric": "ppda"},  # the id says possession
        {"scope": "NGT"},
        {"window": "15m"},
        {"asOfSeq": 9},
        {"matchId": "m43", "inputs": []},
    ],
)
def test_the_id_must_name_exactly_this_snapshot(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="id"):
        parse_metric_snapshot(SNAPSHOT | overrides)


def test_a_restatement_supersedes_the_same_key_at_the_previous_version() -> None:
    with pytest.raises(ValidationError, match="supersede"):
        parse_metric_snapshot(
            SNAPSHOT
            | {
                "snapshotId": "ms-m42-possession-HCY-5m-s0187-v3",
                "version": 3,
                "supersedes": "ms-m42-possession-HCY-5m-s0187-v1",
            }
        )


@pytest.mark.parametrize(("metric", "scope"), [("control_chaos", "HCY"), ("possession", "match")])
def test_metric_and_scope_must_agree(metric: str, scope: str) -> None:
    snapshot_id = f"ms-m42-{metric}-{scope}-5m-s0187-v1"
    with pytest.raises(ValidationError, match="scope"):
        parse_metric_snapshot(
            SNAPSHOT | {"metric": metric, "scope": scope, "snapshotId": snapshot_id}
        )


@pytest.mark.parametrize("inputs", [["m42-e0151", "m42-e0150"], ["m42-e0150", "m42-e0150"]])
def test_evidence_is_unique_and_in_match_order(inputs: list[str]) -> None:
    with pytest.raises(ValidationError, match="evidence"):
        parse_metric_snapshot(SNAPSHOT | {"inputs": inputs})


def test_snapshot_ids_are_bounded_in_length() -> None:
    with pytest.raises(ValidationError):
        parse_metric_snapshot(SNAPSHOT | {"snapshotId": "ms-m42-" + "a" * 500 + "-HCY-5m-s0187-v1"})
