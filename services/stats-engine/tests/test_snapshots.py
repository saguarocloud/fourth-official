"""Snapshots: metrics frozen at a moment, over a window, with stable identity and evidence."""

import time

import pytest

from events import pass_, period_end, pressure, shot
from fourth_official_contracts import MetricSnapshot, parse_metric_snapshot
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import prepare
from fourth_official_stats.snapshots import (
    SnapshotKey,
    publishable,
    snapshot,
    snapshots_at,
    window_events,
)

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")
RAW = (
    pass_(1, 2, "HCY"),
    pass_(2, 8, "HCY"),
    pass_(3, 12, "NGT"),
    pressure(4, 13, "HCY", "NGT"),
    pass_(5, 14, "HCY", second=30),
    shot(6, 15, "HCY"),
    pass_(7, 16, "NGT"),  # after the moment we freeze at
)
EVENTS = prepare(CTX, RAW)


def test_a_five_minute_window_holds_events_from_the_last_five_minutes_up_to_the_moment() -> None:
    window = window_events(EVENTS, as_of_seq=6, window="5m")

    # As of 15:00, the window is (10:00, 15:00].
    assert [e.seq for e in window] == [3, 4, 5, 6]


def test_the_match_window_holds_everything_so_far_and_nothing_later() -> None:
    assert [e.seq for e in window_events(EVENTS, as_of_seq=6, window="match")] == [1, 2, 3, 4, 5, 6]


def test_a_snapshot_carries_a_deterministic_id_its_moment_and_its_evidence() -> None:
    result = snapshot(EVENTS, as_of_seq=6, key=SnapshotKey("possession", "HCY", "5m"))

    assert result.snapshot_id == "ms-m42-possession-HCY-5m-s0006-v1"
    assert (result.as_of.minute, result.as_of.second, result.as_of_seq) == (15, 0, 6)
    assert result.value == pytest.approx(0.5)  # HCY 1 of the 2 passes in the window
    assert result.inputs == ("m42-e0003", "m42-e0005")
    assert (result.version, result.supersedes) == (1, None)


def test_snapshots_survive_the_wire() -> None:
    result = snapshot(EVENTS, as_of_seq=6, key=SnapshotKey("xg", "HCY", "match"))

    assert parse_metric_snapshot(result.to_wire()) == result


def test_values_are_rounded_to_four_decimals_for_stable_publishing() -> None:
    result = snapshot(EVENTS, as_of_seq=6, key=SnapshotKey("xg", "HCY", "match"))

    assert result.value is not None
    assert result.value == round(result.value, 4)


def test_the_match_wide_metric_uses_the_match_scope() -> None:
    result = snapshot(EVENTS, as_of_seq=6, key=SnapshotKey("control_chaos", "match", "15m"))

    assert result.scope == "match"


def test_a_team_metric_refuses_the_match_scope_and_vice_versa() -> None:
    with pytest.raises(ValueError, match="scope"):
        snapshot(EVENTS, as_of_seq=6, key=SnapshotKey("possession", "match", "5m"))
    with pytest.raises(ValueError, match="scope"):
        snapshot(EVENTS, as_of_seq=6, key=SnapshotKey("control_chaos", "HCY", "5m"))


def test_an_unknown_moment_is_refused() -> None:
    with pytest.raises(ValueError, match="seq"):
        snapshot(EVENTS, as_of_seq=99, key=SnapshotKey("possession", "HCY", "5m"))


def test_snapshots_at_cover_every_metric_scope_and_window() -> None:
    every = snapshots_at(EVENTS, as_of_seq=6)

    # 10 team metrics x 2 clubs + 1 match metric, over 3 windows.
    assert len(every) == (10 * 2 + 1) * 3
    assert all(isinstance(s, MetricSnapshot) for s in every)
    assert len({s.snapshot_id for s in every}) == len(every)


def test_evidence_never_reaches_beyond_the_moment_or_the_window() -> None:
    for result in snapshots_at(EVENTS, as_of_seq=6):
        allowed = {e.event_id for e in window_events(EVENTS, as_of_seq=6, window=result.window)}
        assert set(result.inputs) <= allowed


def test_the_window_start_is_exclusive() -> None:
    # As of 15:00, an event at exactly 10:00 is outside the 5-minute window.
    match = prepare(CTX, (pass_(1, 10, "HCY"), pass_(2, 15, "HCY")))

    assert [e.seq for e in window_events(match, as_of_seq=2, window="5m")] == [2]


def test_rates_use_at_least_one_minute_and_never_more_than_has_elapsed() -> None:
    early = prepare(CTX, (pressure(1, 0, "HCY", "NGT"),))
    three_minutes = prepare(CTX, (pressure(1, 1, "HCY", "NGT"), pressure(2, 3, "HCY", "NGT")))

    first = snapshot(early, as_of_seq=1, key=SnapshotKey("pressing_intensity", "HCY", "5m"))
    later = snapshot(three_minutes, as_of_seq=2, key=SnapshotKey("pressing_intensity", "HCY", "5m"))

    assert first.value == 1.0  # one press over the one-minute floor
    assert later.value == 0.6667  # two presses over the three minutes played, rounded


def test_windows_run_across_half_time_on_continuous_match_time() -> None:
    # First half ends at 48:00 (three minutes added). As of 46:00 in the second half, five minutes
    # of match time reach back to 47:00 of the first half: the 47:30 pass is in, 42:00 is out.
    raw = (
        pass_(1, 42, "HCY"),
        pass_(2, 47, "HCY", second=30, period=1),
        period_end(3, 48),
        pass_(4, 46, "NGT"),
    )
    match = prepare(CTX, raw)

    assert [e.seq for e in window_events(match, as_of_seq=4, window="5m")] == [2, 3, 4]


def test_negative_zero_is_never_published() -> None:
    assert repr(publishable(-0.00001)) == "0.0"
    assert publishable(None) is None


def test_a_full_match_of_snapshots_is_fast() -> None:
    raw = tuple(pass_(i, min(i // 30, 89), "HCY" if i % 2 else "NGT") for i in range(1, 2701))
    match = prepare(CTX, raw)

    started = time.perf_counter()
    snapshots_at(match, as_of_seq=2700)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.5
