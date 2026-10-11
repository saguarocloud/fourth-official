"""Find moments in a prepared match, deterministically and incrementally.

Event moments (goals, big chances, sendings-off, VAR overturns) are read off single events.
Shift moments (a press that collapses or surges) are checked once per minute of match time from
metric snapshots, and must hold for consecutive checks. Thresholds live in `rules.py`.
"""

import bisect
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Literal

from fourth_official_contracts import (
    CardEvent,
    GoalEvent,
    MatchEvent,
    MetricShift,
    MetricSnapshot,
    Moment,
    MomentKind,
    ShotEvent,
    VarCheckEvent,
    VarDecisionEvent,
    moment_id_for,
)
from fourth_official_moments import rules
from fourth_official_stats.prepare import PreparedMatch
from fourth_official_stats.snapshots import SnapshotKey, snapshot
from fourth_official_stats.xg import PENALTY_XG, shot_xg

ShiftKind = Literal["pressing_collapse", "pressing_surge"]
SHIFT_KINDS: tuple[ShiftKind, ...] = ("pressing_collapse", "pressing_surge")
_NO_COUNTS: MappingProxyType[tuple[str, str], int] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class DetectorState:
    """Where detection got to: the last event read, the last minute checked, how long each shift
    has held, and until when each kind of shift is quiet for each club."""

    last_seq: int = 0
    checked_minute: int = 0
    streaks: MappingProxyType[tuple[str, str], int] = field(default=_NO_COUNTS)
    quiet_until: MappingProxyType[tuple[str, str], int] = field(default=_NO_COUNTS)


def _moment(
    match: PreparedMatch,
    event: MatchEvent,
    kind: MomentKind,
    club: str,
    *,
    evidence: tuple[MatchEvent, ...] = (),
    shifts: tuple[MetricShift, ...] = (),
) -> Moment:
    ordered = sorted({e.event_id: e for e in evidence}.values(), key=lambda e: e.seq)
    snapshots = tuple(i for s in shifts for i in (s.before_snapshot_id, s.after_snapshot_id))
    return Moment(
        moment_id=moment_id_for(match.context.match_id, kind=kind, club=club, as_of_seq=event.seq),
        match_id=match.context.match_id,
        kind=kind,
        club=club,
        as_of_seq=event.seq,
        clock=event.clock,
        event_ids=tuple(e.event_id for e in ordered),
        metric_snapshot_ids=snapshots,
        shifts=shifts,
    )


# --- Event moments --------------------------------------------------------------------------------


def _by_id(match: PreparedMatch, event_id: str | None) -> MatchEvent | None:
    return next((e for e in match.events if e.event_id == event_id), None) if event_id else None


def _event_moment(match: PreparedMatch, event: MatchEvent) -> Moment | None:
    if isinstance(event, GoalEvent):
        shot = _by_id(match, event.shot_event_id)
        evidence = (event,) if shot is None else (shot, event)
        return _moment(match, event, "goal", event.team_id, evidence=evidence)
    if isinstance(event, ShotEvent) and event.outcome != "goal":
        award_id = match.penalty_awards.get(event.event_id)
        value = PENALTY_XG if award_id else shot_xg(event, match.context)
        if value < rules.BIG_CHANCE_XG:
            return None
        award = _by_id(match, award_id)
        evidence = (event,) if award is None else (award, event)
        return _moment(match, event, "big_chance", event.team_id, evidence=evidence)
    if isinstance(event, CardEvent) and event.card in {"red", "second_yellow"}:
        foul = _by_id(match, event.foul_event_id)
        evidence = (event,) if foul is None else (foul, event)
        return _moment(match, event, "red_card", event.team_id, evidence=evidence)
    if isinstance(event, VarDecisionEvent) and event.decision == "overturned":
        return _overturn(match, event)
    return None


def _overturn(match: PreparedMatch, decision: VarDecisionEvent) -> Moment | None:
    target = _by_id(match, decision.target_event_id)
    club = getattr(target, "team_id", None)
    if target is None or club is None:
        return None
    checks = tuple(
        e
        for e in match.events
        if isinstance(e, VarCheckEvent)
        and e.target_event_id == target.event_id
        and e.seq < decision.seq
    )
    return _moment(match, decision, "var_overturn", club, evidence=(target, *checks, decision))


# --- Shift moments --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Timeline:
    """Monotone match seconds of every event, for finding the last event at a given time."""

    match: PreparedMatch
    seconds: tuple[int, ...]

    @classmethod
    def of(cls, match: PreparedMatch) -> "_Timeline":
        return cls(match, tuple(match.seconds(e) for e in match.events))

    def last_at(self, second: int) -> MatchEvent | None:
        index = bisect.bisect_right(self.seconds, second) - 1
        return self.match.events[index] if index >= 0 else None


def _press_shift(
    timeline: _Timeline, now: MatchEvent, club: str
) -> tuple[ShiftKind, MetricShift] | None:
    """Whether the club's press has collapsed or surged as of `now`, with the evidence."""
    match = timeline.match
    lag = match.seconds(now) - rules.PRESS_BASELINE_LAG_MINUTES * 60
    then = timeline.last_at(lag)
    if then is None:
        return None
    before = _snap(match, then, club, rules.PRESS_BASELINE_WINDOW)
    after = _snap(match, now, club, rules.PRESS_CURRENT_WINDOW)
    if before.value is None or after.value is None:
        return None
    kind: ShiftKind | None = None
    if (
        before.value >= rules.PRESS_FLOOR
        and after.value <= rules.PRESS_COLLAPSE_RATIO * before.value
    ):
        kind = "pressing_collapse"
    elif (
        after.value >= rules.PRESS_FLOOR
        and before.value > 0
        and after.value >= rules.PRESS_SURGE_RATIO * before.value
    ):
        kind = "pressing_surge"
    if kind is None:
        return None
    shift = MetricShift(
        metric="pressing_intensity",
        before=before.value,
        after=after.value,
        before_snapshot_id=before.snapshot_id,
        after_snapshot_id=after.snapshot_id,
    )
    return kind, shift


def _snap(match: PreparedMatch, at: MatchEvent, club: str, window: str) -> MetricSnapshot:
    key = SnapshotKey("pressing_intensity", club, window)  # type: ignore[arg-type]
    return snapshot(match, as_of_seq=at.seq, key=key)


def _check_shifts(
    timeline: _Timeline, state: DetectorState, now: MatchEvent, minute: int
) -> tuple[DetectorState, list[Moment]]:
    match = timeline.match
    streaks, quiet = dict(state.streaks), dict(state.quiet_until)
    found: list[Moment] = []
    for club in (match.context.home, match.context.away):
        result = _press_shift(timeline, now, club)
        for kind in SHIFT_KINDS:
            key = (kind, club)
            held = result is not None and result[0] == kind
            streaks[key] = streaks.get(key, 0) + 1 if held else 0
            if result is None or not held or streaks[key] < rules.PERSIST_CHECKS:
                continue
            if minute < quiet.get(key, 0):
                continue
            found.append(_moment(match, now, kind, club, shifts=(result[1],)))
            quiet[key] = minute + rules.COOLDOWN_MINUTES
            streaks[key] = 0
    return (
        replace(
            state,
            checked_minute=minute,
            streaks=MappingProxyType(streaks),
            quiet_until=MappingProxyType(quiet),
        ),
        found,
    )


# --- Detection ------------------------------------------------------------------------------------


def detect(
    match: PreparedMatch, state: DetectorState | None = None
) -> tuple[DetectorState, tuple[Moment, ...]]:
    """Moments among the events after `state.last_seq`, in the order they were found, and the
    state to resume from. Detecting a whole match at once gives the same moments as detecting it
    piece by piece."""
    state = state or DetectorState()
    timeline = _Timeline.of(match)
    found: list[Moment] = []
    for event in match.events:
        if event.seq <= state.last_seq:
            continue
        minute = match.seconds(event) // 60
        if minute > state.checked_minute and minute >= rules.FIRST_CHECK_MINUTE:
            state, shifted = _check_shifts(timeline, state, event, minute)
            found += shifted
        moment = _event_moment(match, event)
        if moment is not None:
            found.append(moment)
        state = replace(state, last_seq=event.seq)
    return state, tuple(found)
