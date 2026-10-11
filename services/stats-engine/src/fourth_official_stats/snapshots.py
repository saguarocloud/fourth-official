"""Freeze metrics into snapshots: one metric, one scope, one window, at one moment of the match."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import get_args

from fourth_official_contracts import (
    MatchEvent,
    MetricName,
    MetricSnapshot,
    MetricWindow,
    snapshot_id_for,
)
from fourth_official_stats import metrics
from fourth_official_stats.context import MatchContext
from fourth_official_stats.metrics import MetricValue
from fourth_official_stats.prepare import PreparedMatch

WINDOW_SECONDS: dict[MetricWindow, int | None] = {"5m": 5 * 60, "15m": 15 * 60, "match": None}
VALUE_DECIMALS = 4
MATCH_SCOPE = "match"

TeamMetric = Callable[[Sequence[MatchEvent], MatchContext, str], MetricValue]
TEAM_METRICS: dict[MetricName, TeamMetric] = {
    "possession": metrics.possession,
    "field_tilt": metrics.field_tilt,
    "passes": metrics.passes,
    "pass_completion": metrics.pass_completion,
    "shots": metrics.shots,
    "shots_on_target": metrics.shots_on_target,
    "xg": metrics.xg,
    "ppda": metrics.ppda,
    "momentum": metrics.momentum,
}
MATCH_METRICS: frozenset[MetricName] = frozenset({"control_chaos"})


@dataclass(frozen=True, slots=True)
class SnapshotKey:
    """What a snapshot measures: one metric, for one scope, over one window."""

    metric: MetricName
    scope: str
    window: MetricWindow


@dataclass(frozen=True, slots=True)
class _Window:
    events: tuple[MatchEvent, ...]
    minutes: float


def publishable(value: float | None) -> float | None:
    """Round for publishing; never emit -0.0, which a verifier would read as a different number."""
    return None if value is None else round(value, VALUE_DECIMALS) + 0.0


def _moment(match: PreparedMatch, as_of_seq: int) -> MatchEvent:
    moment = match.by_seq.get(as_of_seq)
    if moment is None:
        raise ValueError(f"no event with seq {as_of_seq} in match {match.context.match_id}")
    return moment


def window_events(
    match: PreparedMatch, *, as_of_seq: int, window: MetricWindow
) -> tuple[MatchEvent, ...]:
    """Events the window can see: up to and including the moment, and within its duration on the
    monotone match timeline (the start is exclusive)."""
    now = match.seconds(_moment(match, as_of_seq))
    span = WINDOW_SECONDS[window]
    return tuple(
        e
        for e in match.events
        if e.seq <= as_of_seq and (span is None or match.seconds(e) > now - span)
    )


def _window(match: PreparedMatch, as_of_seq: int, window: MetricWindow) -> _Window:
    now = match.seconds(_moment(match, as_of_seq))
    span = WINDOW_SECONDS[window]
    covered = now if span is None else min(span, now)
    # Per-minute rates use the window's length, capped at time played, with a one-minute floor.
    return _Window(window_events(match, as_of_seq=as_of_seq, window=window), max(covered, 60) / 60)


def _compute(context: MatchContext, key: SnapshotKey, window: _Window) -> MetricValue:
    if key.metric in MATCH_METRICS:
        if key.scope != MATCH_SCOPE:
            raise ValueError(f"{key.metric} is a match-wide metric; use scope {MATCH_SCOPE!r}")
        return metrics.control_chaos(window.events, context, minutes=window.minutes)
    if key.scope == MATCH_SCOPE:
        raise ValueError(f"{key.metric} is measured per club; scope must be a club code")
    if key.metric == "pressing_intensity":
        return metrics.pressing_intensity(window.events, context, key.scope, minutes=window.minutes)
    return TEAM_METRICS[key.metric](window.events, context, key.scope)


def _freeze(
    match: PreparedMatch, as_of_seq: int, key: SnapshotKey, window: _Window
) -> MetricSnapshot:
    moment = _moment(match, as_of_seq)
    result = _compute(match.context, key, window)
    return MetricSnapshot(
        snapshot_id=snapshot_id_for(
            match.context.match_id,
            metric=key.metric,
            scope=key.scope,
            window=key.window,
            as_of_seq=as_of_seq,
            version=1,
        ),
        match_id=match.context.match_id,
        metric=key.metric,
        scope=key.scope,
        window=key.window,
        as_of=moment.clock,
        as_of_seq=as_of_seq,
        value=publishable(result.value),
        inputs=result.inputs,
        version=1,
        supersedes=None,
    )


def snapshot(match: PreparedMatch, *, as_of_seq: int, key: SnapshotKey) -> MetricSnapshot:
    """One metric for one scope over one window, as of the event with `as_of_seq`."""
    return _freeze(match, as_of_seq, key, _window(match, as_of_seq, key.window))


def snapshot_keys(context: MatchContext) -> tuple[SnapshotKey, ...]:
    """Every metric, for both clubs (and the match), over every window."""
    keys = []
    for window in get_args(MetricWindow):
        for metric in get_args(MetricName):
            if metric in MATCH_METRICS:
                keys.append(SnapshotKey(metric, MATCH_SCOPE, window))
            else:
                keys.extend(
                    SnapshotKey(metric, club, window) for club in (context.home, context.away)
                )
    return tuple(keys)


def snapshots_at(match: PreparedMatch, *, as_of_seq: int) -> tuple[MetricSnapshot, ...]:
    """Every snapshot key at one moment; each window is cut once and shared by all its metrics."""
    windows = {w: _window(match, as_of_seq, w) for w in get_args(MetricWindow)}
    return tuple(
        _freeze(match, as_of_seq, key, windows[key.window]) for key in snapshot_keys(match.context)
    )
