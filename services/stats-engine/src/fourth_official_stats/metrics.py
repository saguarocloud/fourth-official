"""Metrics over a window of match events. Each returns its value and its evidence.

Formulas, coefficients and sources are documented in docs/metrics.md. All functions are pure.
"""

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from fourth_official_contracts import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    CarryEvent,
    FoulEvent,
    InterceptionEvent,
    MatchEvent,
    PassEvent,
    PossessionChangeEvent,
    PressureEvent,
    ShotEvent,
    TackleEvent,
)
from fourth_official_stats.context import MatchContext
from fourth_official_stats.xg import PENALTY_XG, penalty_awards, shot_xg

# The last third of the pitch, from the attacking team's point of view.
FINAL_THIRD_FROM = 2 / 3
# PPDA counts the opponent's passes in its own 60% of the pitch.
PPDA_BUILD_UP_ZONE = 0.6
# Pass difficulty weights and kind factors.
DIFFICULTY_DISTANCE_M = 50.0
DIFFICULTY_WEIGHTS = (0.45, 0.35, 0.2)  # distance, pressure, kind
KIND_FACTOR = {"ground": 0.2, "lofted": 0.5, "switch": 0.6, "cross": 0.7, "through": 0.8}
# Control-versus-chaos: saturation points and weights.
CHAOS_TURNOVERS_PER_MINUTE = 4.0
CHAOS_CHAIN_PASSES = 8.0
CHAOS_WEIGHTS = (0.4, 0.4, 0.2)  # turnovers, short chains, spatial entropy
ENTROPY_GRID = (6, 4)


@dataclass(frozen=True, slots=True)
class MetricValue:
    value: float | None
    # Event IDs the value was computed from, in match order.
    inputs: tuple[str, ...]


def _ids(events: Iterable[MatchEvent]) -> tuple[str, ...]:
    return tuple(e.event_id for e in sorted(events, key=lambda e: e.seq))


def _passes(events: Iterable[MatchEvent], team: str | None = None) -> list[PassEvent]:
    return [e for e in events if isinstance(e, PassEvent) and (team is None or e.team_id == team)]


def _shots(events: Iterable[MatchEvent], team: str | None = None) -> list[ShotEvent]:
    return [e for e in events if isinstance(e, ShotEvent) and (team is None or e.team_id == team)]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


# --- Passing and possession ------------------------------------------------------------------


def passes(events: Sequence[MatchEvent], context: MatchContext, team: str) -> MetricValue:
    own = _passes(events, team)
    return MetricValue(float(len(own)), _ids(own))


def pass_completion(events: Sequence[MatchEvent], context: MatchContext, team: str) -> MetricValue:
    own = _passes(events, team)
    completed = sum(p.outcome == "complete" for p in own)
    return MetricValue(_ratio(completed, len(own)), _ids(own))


def possession(events: Sequence[MatchEvent], context: MatchContext, team: str) -> MetricValue:
    """Share of all passes made by the team: the standard event-data proxy for possession."""
    every = _passes(events)
    return MetricValue(_ratio(sum(p.team_id == team for p in every), len(every)), _ids(every))


def field_tilt(events: Sequence[MatchEvent], context: MatchContext, team: str) -> MetricValue:
    """Share of all final-third passes made by the team."""
    final_third = [
        p
        for p in _passes(events)
        if context.progress(p.team_id, p.clock.period, p.origin.x) >= FINAL_THIRD_FROM
    ]
    own = sum(p.team_id == team for p in final_third)
    return MetricValue(_ratio(own, len(final_third)), _ids(final_third))


def pressure_on_passer(pass_event: PassEvent, by_seq: Mapping[int, MatchEvent]) -> float:
    """Intensity of a pressure event on the passer immediately before the pass (by sequence
    number: the feed records a press right before the action it affects), or 0."""
    before = by_seq.get(pass_event.seq - 1)
    if isinstance(before, PressureEvent) and before.target_id == pass_event.player_id:
        return before.intensity
    return 0.0


def pass_difficulty(pass_event: PassEvent, *, pressure: float) -> float:
    """0-100: how hard a pass was, from its distance, the pressure on the passer and its kind."""
    distance = math.hypot(
        pass_event.end.x - pass_event.origin.x, pass_event.end.y - pass_event.origin.y
    )
    w_distance, w_pressure, w_kind = DIFFICULTY_WEIGHTS
    rating = (
        w_distance * min(distance / DIFFICULTY_DISTANCE_M, 1.0)
        + w_pressure * pressure
        + w_kind * KIND_FACTOR[pass_event.kind]
    )
    return round(100.0 * rating, 1)


# --- Shooting --------------------------------------------------------------------------------


def shots(events: Sequence[MatchEvent], context: MatchContext, team: str) -> MetricValue:
    own = _shots(events, team)
    return MetricValue(float(len(own)), _ids(own))


def shots_on_target(events: Sequence[MatchEvent], context: MatchContext, team: str) -> MetricValue:
    own = _shots(events, team)
    return MetricValue(float(sum(s.outcome in {"goal", "saved"} for s in own)), _ids(own))


def _shot_values(
    shots_: Sequence[ShotEvent], context: MatchContext, penalties: Mapping[str, str]
) -> dict[str, float]:
    return {
        s.event_id: PENALTY_XG if s.event_id in penalties else shot_xg(s, context) for s in shots_
    }


def _shot_evidence(shots_: Sequence[ShotEvent], penalties: Mapping[str, str]) -> tuple[str, ...]:
    """The shots, each preceded by the penalty award that decided its value, if any. An award is
    always the event straight before its shot, so this is match order."""
    evidence: list[str] = []
    for shot in sorted(shots_, key=lambda s: s.seq):
        if shot.event_id in penalties:
            evidence.append(penalties[shot.event_id])
        evidence.append(shot.event_id)
    return tuple(evidence)


def xg(
    events: Sequence[MatchEvent],
    context: MatchContext,
    team: str,
    *,
    penalties: Mapping[str, str] | None = None,
) -> MetricValue:
    """Expected goals. `penalties` maps penalty shots to their awards; by default it is worked out
    from `events`, but a snapshot passes the whole match's so a window never cuts a penalty off
    from its award."""
    known = penalty_awards(events) if penalties is None else penalties
    own = _shots(events, team)
    values = _shot_values(own, context, known)
    return MetricValue(sum((values[s.event_id] for s in own), 0.0), _shot_evidence(own, known))


def momentum(
    events: Sequence[MatchEvent],
    context: MatchContext,
    team: str,
    *,
    penalties: Mapping[str, str] | None = None,
) -> MetricValue:
    """Expected-goals difference over the window, from the team's side."""
    context.opponent(team)  # refuses a club that is not playing
    known = penalty_awards(events) if penalties is None else penalties
    every = _shots(events)
    values = _shot_values(every, context, known)
    balance = sum((values[s.event_id] * (1 if s.team_id == team else -1) for s in every), 0.0)
    return MetricValue(balance, _shot_evidence(every, known))


# --- Pressing --------------------------------------------------------------------------------


def ppda(events: Sequence[MatchEvent], context: MatchContext, pressing_team: str) -> MetricValue:
    """Passes allowed per defensive action: the opponent's passes in its own 60% of the pitch,
    divided by the pressing team's tackles, interceptions and fouls in that same area. Lower means
    a more aggressive press."""
    opponent = context.opponent(pressing_team)
    allowed = [
        p
        for p in _passes(events, opponent)
        if context.progress(opponent, p.clock.period, p.origin.x) <= PPDA_BUILD_UP_ZONE
    ]
    actions = [
        e
        for e in events
        if isinstance(e, TackleEvent | InterceptionEvent | FoulEvent)
        and e.team_id == pressing_team
        and context.progress(opponent, e.clock.period, e.at.x) <= PPDA_BUILD_UP_ZONE
    ]
    return MetricValue(_ratio(len(allowed), len(actions)), _ids([*allowed, *actions]))


def pressing_intensity(
    events: Sequence[MatchEvent], context: MatchContext, team: str
) -> MetricValue:
    """Pressure events the team applies per opponent pass or carry. Normalising by the opponent's
    touches keeps a side that hoards the ball from making its opponent's press look busier."""
    opponent = context.opponent(team)
    applied = [e for e in events if isinstance(e, PressureEvent) and e.team_id == team]
    touches = [e for e in events if isinstance(e, PassEvent | CarryEvent) and e.team_id == opponent]
    if not touches:
        return MetricValue(None, ())
    return MetricValue(len(applied) / len(touches), _ids([*applied, *touches]))


# --- Control versus chaos --------------------------------------------------------------------


def _location(event: MatchEvent) -> tuple[float, float] | None:
    for name in ("origin", "at"):
        point = getattr(event, name, None)
        if point is not None:
            return point.x, point.y
    return None


def _spatial_entropy(points: list[tuple[float, float]]) -> float:
    """Shannon entropy of locations over a coarse grid, normalised to 0..1."""
    columns, rows = ENTROPY_GRID
    if not points:
        return 0.0
    cells = Counter(
        (
            min(int(x / PITCH_LENGTH_M * columns), columns - 1),
            min(int(y / PITCH_WIDTH_M * rows), rows - 1),
        )
        for x, y in points
    )
    total = len(points)
    entropy = -sum((n / total) * math.log(n / total) for n in cells.values())
    return entropy / math.log(columns * rows)


def control_chaos(
    events: Sequence[MatchEvent], context: MatchContext, *, minutes: float
) -> MetricValue:
    """0-100: how chaotic play is. Frequent turnovers, short passing chains and play scattered
    across the pitch push it up; long controlled possessions bring it down."""
    turnovers = [e for e in events if isinstance(e, PossessionChangeEvent)]
    every_pass = _passes(events)
    if minutes <= 0 or not (turnovers or every_pass):
        # Nothing to read: report no value rather than a made-up level of calm or chaos.
        return MetricValue(None, ())
    located = [(e, loc) for e in events if (loc := _location(e)) is not None]
    turnover_term = min(len(turnovers) / minutes / CHAOS_TURNOVERS_PER_MINUTE, 1.0)
    mean_chain = len(every_pass) / (len(turnovers) + 1)
    chain_term = 1.0 - min(mean_chain / CHAOS_CHAIN_PASSES, 1.0)
    entropy_term = _spatial_entropy([loc for _, loc in located])
    w_turnover, w_chain, w_entropy = CHAOS_WEIGHTS
    index = 100.0 * (w_turnover * turnover_term + w_chain * chain_term + w_entropy * entropy_term)
    inputs = {e.event_id: e for e in [*turnovers, *every_pass, *(e for e, _ in located)]}
    return MetricValue(index, _ids(inputs.values()))
