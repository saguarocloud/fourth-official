"""Snapshots by ID, computed on demand: whatever a tool served can be checked later."""

from explain_fixtures import featured
from fourth_official_explain.snapshots import ComputedSnapshots


def test_a_served_snapshot_is_found_by_its_id() -> None:
    facts, moments = featured()
    collapse = next(m for m in moments if m.kind == "pressing_collapse")

    for snapshot_id in collapse.metric_snapshot_ids:
        found = facts.snapshots.get(snapshot_id)
        assert found is not None
        assert found.snapshot_id == snapshot_id
        assert snapshot_id in facts.snapshots  # type: ignore[operator]


def test_ids_that_do_not_name_a_first_version_snapshot_of_this_match_are_absent() -> None:
    facts, _ = featured()
    snapshots = facts.snapshots
    assert isinstance(snapshots, ComputedSnapshots)

    for missing in (
        "ms-m43-xg-KBA-5m-s0100-v1",  # another match
        "ms-m42-xg-HCY-5m-s0100-v2",  # a restatement it never published
        "ms-m42-vibes-HCY-5m-s0100-v1",  # no such metric
        "ms-m42-xg-HCY-5m-s9999-v1",  # no such moment
        "ms-m42-xg-HCY-5m-s00100-v1",  # not how that snapshot's ID is written
        "not a snapshot id",
    ):
        assert snapshots.get(missing) is None
    assert 42 not in snapshots


def test_lookups_for_different_matches_are_never_equal() -> None:
    facts, _ = featured()
    other = ComputedSnapshots(facts.match)

    lookup: object = facts.snapshots
    assert lookup != other
    assert lookup != {}
