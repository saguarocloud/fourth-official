"""The match engine: a seeded possession-chain simulation that emits contract-valid match events.

The match advances one *phase* at a time: the player on the ball may be pressed, may be fouled,
then chooses an action (pass, carry, cross, shot) whose success depends on distance, pressure and
team style. Every transition is a pure function of a frozen `MatchState` and a seeded random
generator, so a setup and seed always produce exactly the same match.
"""

import random
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal, TypedDict

from fourth_official_contracts import (
    CardEvent,
    CarryEvent,
    FoulEvent,
    GoalEvent,
    InterceptionEvent,
    MatchClock,
    MatchEvent,
    OffsideEvent,
    PassEvent,
    PeriodEndEvent,
    PeriodStartEvent,
    PitchPoint,
    PossessionChangeEvent,
    PressureEvent,
    SaveEvent,
    Score,
    SetPieceEvent,
    ShotEvent,
    SubstitutionEvent,
    TackleEvent,
)
from fourth_official_simulator.pitch import (
    Zone,
    attacking_to_pitch,
    distance_to_goal,
    shooting_angle,
    zone_of,
)
from fourth_official_simulator.probabilities import (
    Action,
    PassKind,
    choose_action,
    expected_goals,
    pass_completion,
)
from fourth_official_simulator.squads import Player, Position, Squad, starting_xi
from fourth_official_simulator.style import TeamStyle

HALF_SECONDS = 45 * 60
HALF_TIME_BREAK = timedelta(minutes=15)
MAX_SUBSTITUTIONS = 3
# Base rates per phase, tuned so whole matches land in public aggregate ranges.
PRESS_RATE = 0.55
FOUL_RATE = 0.015
YELLOW_GIVEN_FOUL = 0.13
RED_GIVEN_FOUL = 0.004
OFFSIDE_GIVEN_THROUGH_BALL = 0.06
OUT_OF_PLAY_GIVEN_MISS = 0.35
SHOT_ON_TARGET_GIVEN_MISS = 0.3
BLOCKED_GIVEN_OFF_TARGET = 0.3
CORNER_GIVEN_BLOCK_OR_SAVE = 0.4

Period = Literal[1, 2]
SetPieceKind = Literal["kick_off", "corner", "free_kick", "throw_in", "goal_kick", "penalty"]
CardKind = Literal["yellow", "second_yellow", "red"]
ShotOutcome = Literal["goal", "saved", "off_target", "blocked", "woodwork"]
PossessionCause = Literal["tackle", "interception", "out_of_play", "foul", "shot_end", "other"]


@dataclass(frozen=True, slots=True)
class TeamSetup:
    squad: Squad
    formation: str
    style: TeamStyle


@dataclass(frozen=True, slots=True)
class MatchSetup:
    match_id: str
    seed: int
    kickoff: datetime
    home: TeamSetup
    away: TeamSetup


@dataclass(frozen=True, slots=True)
class Side:
    """One team's in-match situation."""

    club: str
    style: TeamStyle
    on_pitch: tuple[Player, ...]
    bench: tuple[Player, ...]
    booked: frozenset[str] = frozenset()
    substitutions: int = 0
    sub_minutes: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchState:
    period: Period
    elapsed: int  # seconds since kick-off of the match clock (period 2 starts at 45:00)
    period_end: int  # seconds at which the current period ends, including added time
    seq: int
    home: Side
    away: Side
    home_in_possession: bool
    carrier: Player
    progress: float  # 0 = own goal line, 1 = opponent goal line (attacking frame)
    lateral: float
    home_score: int = 0
    away_score: int = 0
    # The player whose completed pass reached the current carrier, if the last action was one.
    last_passer: Player | None = None


class Envelope(TypedDict):
    event_id: str
    match_id: str
    seq: int
    version: int
    clock: MatchClock
    wall_clock: datetime


@dataclass(frozen=True, slots=True)
class _Emitter:
    """Builds the envelope (identity, clock, wall-clock time) for each new event."""

    setup: MatchSetup

    def envelope(self, state: MatchState, seq: int) -> Envelope:
        minute, second = divmod(state.elapsed, 60)
        break_offset = HALF_TIME_BREAK if state.period == 2 else timedelta()
        return {
            "event_id": f"{self.setup.match_id}-e{seq:04d}",
            "match_id": self.setup.match_id,
            "seq": seq,
            "version": 1,
            "clock": MatchClock(period=state.period, minute=minute, second=second),
            "wall_clock": self.setup.kickoff + timedelta(seconds=state.elapsed) + break_offset,
        }


# --- Helpers -------------------------------------------------------------------------------------


def _side(state: MatchState, home: bool) -> Side:
    return state.home if home else state.away


def _attackers(state: MatchState) -> Side:
    return _side(state, state.home_in_possession)


def _defenders(state: MatchState) -> Side:
    return _side(state, not state.home_in_possession)


def _point(state: MatchState, progress: float, lateral: float, *, home: bool) -> PitchPoint:
    x, y = attacking_to_pitch(progress, lateral, home=home, period=state.period)
    return PitchPoint(x=x, y=y)


_ROLE_WEIGHTS: dict[Zone, dict[Position, float]] = {
    Zone.DEFENSIVE_THIRD: {
        Position.GOALKEEPER: 1.0,
        Position.DEFENDER: 5.0,
        Position.MIDFIELDER: 3.0,
        Position.FORWARD: 0.5,
    },
    Zone.MIDDLE_THIRD: {
        Position.GOALKEEPER: 0.0,
        Position.DEFENDER: 2.5,
        Position.MIDFIELDER: 5.0,
        Position.FORWARD: 2.0,
    },
    Zone.FINAL_THIRD: {
        Position.GOALKEEPER: 0.0,
        Position.DEFENDER: 1.0,
        Position.MIDFIELDER: 4.0,
        Position.FORWARD: 4.0,
    },
    Zone.BOX: {
        Position.GOALKEEPER: 0.0,
        Position.DEFENDER: 0.5,
        Position.MIDFIELDER: 2.0,
        Position.FORWARD: 6.0,
    },
}


def _pick(
    players: tuple[Player, ...], zone: Zone, rng: random.Random, exclude: Player | None = None
) -> Player:
    candidates = [p for p in players if p != exclude] or list(players)
    weights = [_ROLE_WEIGHTS[zone][p.position] + 0.05 for p in candidates]
    return rng.choices(candidates, weights=weights)[0]


def _keeper(side: Side) -> Player:
    keepers = [p for p in side.on_pitch if p.position is Position.GOALKEEPER]
    return keepers[0] if keepers else side.on_pitch[0]


def _with_side(state: MatchState, home: bool, side: Side) -> MatchState:
    return replace(state, home=side) if home else replace(state, away=side)


def _advance(state: MatchState, seconds: float, style: TeamStyle) -> MatchState:
    # Higher tempo means quicker phases.
    duration = max(1, round(seconds * (1.35 - 0.6 * style.tempo)))
    return replace(state, elapsed=min(state.elapsed + duration, state.period_end))


def _turnover(
    state: MatchState, new_carrier: Player, progress: float, lateral: float
) -> MatchState:
    # The ball changes hands; the new attacking frame mirrors the old one.
    return replace(
        state,
        home_in_possession=not state.home_in_possession,
        carrier=new_carrier,
        progress=1.0 - progress,
        lateral=1.0 - lateral,
    )


def _restart(
    state: MatchState, home_in_possession: bool, progress: float, lateral: float, rng: random.Random
) -> MatchState:
    side = _side(state, home_in_possession)
    zone = zone_of(progress, lateral)
    return replace(
        state,
        home_in_possession=home_in_possession,
        carrier=_pick(side.on_pitch, zone, rng),
        progress=progress,
        lateral=lateral,
    )


# --- Phase steps (each returns the new state and the events it produced) -------------------------

Step = tuple[MatchState, list[MatchEvent]]


def _set_piece(
    state: MatchState, emit: _Emitter, kind: SetPieceKind, progress: float, lateral: float
) -> Step:
    attackers = _attackers(state)
    seq = state.seq + 1
    event = SetPieceEvent(
        **emit.envelope(state, seq),
        type="SET_PIECE",
        team_id=attackers.club,
        player_id=state.carrier.player_id,
        kind=kind,
        at=_point(state, progress, lateral, home=state.home_in_possession),
    )
    return replace(state, seq=seq), [event]


def _press(
    state: MatchState, emit: _Emitter, rng: random.Random
) -> tuple[MatchState, list[MatchEvent], float]:
    defenders = _defenders(state)
    zone = zone_of(state.progress, state.lateral)
    # Pressing is fiercer in the opponent's half (the attacking team's own third).
    height = 1.3 if zone is Zone.DEFENSIVE_THIRD else 1.0 if zone is Zone.MIDDLE_THIRD else 0.8
    if rng.random() >= PRESS_RATE * defenders.style.pressing * height:
        return state, [], rng.uniform(0.0, 0.25)
    intensity = round(min(1.0, rng.uniform(0.3, 1.0) * (0.6 + defenders.style.pressing * 0.6)), 3)
    presser = _pick(
        defenders.on_pitch,
        Zone.FINAL_THIRD if zone is Zone.DEFENSIVE_THIRD else Zone.MIDDLE_THIRD,
        rng,
    )
    seq = state.seq + 1
    event = PressureEvent(
        **emit.envelope(state, seq),
        type="PRESSURE",
        team_id=defenders.club,
        player_id=presser.player_id,
        at=_point(state, state.progress, state.lateral, home=state.home_in_possession),
        target_id=state.carrier.player_id,
        intensity=intensity,
    )
    return replace(state, seq=seq), [event], intensity


def _foul(state: MatchState, emit: _Emitter, rng: random.Random) -> Step:
    defenders = _defenders(state)
    offender = _pick(defenders.on_pitch, Zone.MIDDLE_THIRD, rng, exclude=_keeper(defenders))
    seq = state.seq + 1
    at = _point(state, state.progress, state.lateral, home=state.home_in_possession)
    foul = FoulEvent(
        **emit.envelope(state, seq),
        type="FOUL",
        team_id=defenders.club,
        player_id=offender.player_id,
        at=at,
        victim_id=state.carrier.player_id,
    )
    events: list[MatchEvent] = [foul]
    roll = rng.random()
    card: CardKind | None = None
    if roll < RED_GIVEN_FOUL:
        card = "red"
    elif roll < RED_GIVEN_FOUL + YELLOW_GIVEN_FOUL:
        card = "second_yellow" if offender.player_id in defenders.booked else "yellow"
    if card is not None:
        seq += 1
        events.append(
            CardEvent(
                **emit.envelope(state, seq),
                type="CARD",
                team_id=defenders.club,
                player_id=offender.player_id,
                card=card,
                foul_event_id=foul.event_id,
            )
        )
        if card == "yellow":
            defenders = replace(defenders, booked=defenders.booked | {offender.player_id})
        else:  # sent off: the team plays on a player short
            defenders = replace(
                defenders, on_pitch=tuple(p for p in defenders.on_pitch if p != offender)
            )
        state = _with_side(state, not state.home_in_possession, defenders)
    state = replace(state, seq=seq)
    state = _advance(state, rng.uniform(25, 45), _attackers(state).style)
    state, set_piece = _set_piece(state, emit, "free_kick", state.progress, state.lateral)
    return state, events + set_piece


def _pass(
    state: MatchState, emit: _Emitter, rng: random.Random, action: Action, pressure: float
) -> Step:
    attackers, defenders = _attackers(state), _defenders(state)
    style = attackers.style
    kind: PassKind
    if action is Action.LONG_PASS:
        kind = "switch" if rng.random() < 0.3 else "lofted"
        forward, sideways = rng.uniform(0.18, 0.4), rng.uniform(-0.45, 0.45)
    elif action is Action.THROUGH_BALL:
        kind, forward, sideways = "through", rng.uniform(0.12, 0.28), rng.uniform(-0.15, 0.15)
    elif action is Action.CROSS:
        kind = "cross"
        forward = max(0.0, 0.95 - state.progress) + rng.uniform(-0.03, 0.03)
        sideways = 0.5 - state.lateral + rng.uniform(-0.12, 0.12)
    else:
        kind = "ground"
        forward = rng.uniform(-0.06, 0.16) + 0.06 * style.directness
        sideways = rng.uniform(-0.2, 0.2) * (0.5 + style.width)
    end_progress = min(max(state.progress + forward, 0.02), 0.99)
    end_lateral = min(max(state.lateral + sideways, 0.02), 0.98)
    distance = ((forward * 105) ** 2 + (sideways * 68) ** 2) ** 0.5
    speed = round(min(140.0, 30 + distance * 1.4 + rng.uniform(-5, 5)), 1)
    completed = rng.random() < pass_completion(distance, pressure, kind=kind)

    if completed and kind == "through" and rng.random() < OFFSIDE_GIVEN_THROUGH_BALL:
        runner = _pick(attackers.on_pitch, Zone.FINAL_THIRD, rng, exclude=state.carrier)
        seq = state.seq + 1
        offside = OffsideEvent(
            **emit.envelope(state, seq),
            type="OFFSIDE",
            team_id=attackers.club,
            player_id=runner.player_id,
            at=_point(state, end_progress, end_lateral, home=state.home_in_possession),
        )
        state = replace(state, seq=seq)
        state = _turnover(state, _keeper(defenders), end_progress, end_lateral)
        state = _advance(state, 20, style)
        state, set_piece = _set_piece(state, emit, "free_kick", state.progress, state.lateral)
        return state, [offside, *set_piece]

    seq = state.seq + 1
    receiver = (
        _pick(attackers.on_pitch, zone_of(end_progress, end_lateral), rng, exclude=state.carrier)
        if completed
        else None
    )
    event = PassEvent(
        **emit.envelope(state, seq),
        type="PASS",
        team_id=attackers.club,
        player_id=state.carrier.player_id,
        origin=_point(state, state.progress, state.lateral, home=state.home_in_possession),
        end=_point(state, end_progress, end_lateral, home=state.home_in_possession),
        outcome="complete" if completed else "incomplete",
        receiver_id=receiver.player_id if receiver else None,
        kind=kind,
        speed_kmh=speed,
    )
    state = replace(state, seq=seq)
    state = _advance(state, 1.5 + distance / 20, style)
    if receiver is not None:
        moved = replace(state, carrier=receiver, progress=end_progress, lateral=end_lateral)
        return replace(moved, last_passer=state.carrier), [event]

    # Incomplete: out of play or intercepted.
    if rng.random() < OUT_OF_PLAY_GIVEN_MISS:
        state = _advance(state, 12, style)
        new_progress, new_lateral = 1.0 - end_progress, 0.0 if end_lateral < 0.5 else 1.0
        state = _restart(state, not state.home_in_possession, new_progress, 1.0 - new_lateral, rng)
        change = _possession_change(state, emit, "out_of_play")
        state = replace(state, seq=change.seq)
        state, set_piece = _set_piece(state, emit, "throw_in", state.progress, state.lateral)
        return state, [event, change.event, *set_piece]
    interceptor = _pick(defenders.on_pitch, zone_of(1 - end_progress, 1 - end_lateral), rng)
    state = _turnover(state, interceptor, end_progress, end_lateral)
    seq = state.seq + 1
    interception = InterceptionEvent(
        **emit.envelope(state, seq),
        type="INTERCEPTION",
        team_id=_attackers(state).club,
        player_id=interceptor.player_id,
        at=_point(state, state.progress, state.lateral, home=state.home_in_possession),
    )
    state = replace(state, seq=seq)
    change = _possession_change(state, emit, "interception")
    return replace(state, seq=change.seq), [event, interception, change.event]


@dataclass(frozen=True, slots=True)
class _Change:
    seq: int
    event: PossessionChangeEvent


def _possession_change(state: MatchState, emit: _Emitter, cause: PossessionCause) -> _Change:
    seq = state.seq + 1
    event = PossessionChangeEvent(
        **emit.envelope(state, seq),
        type="POSSESSION_CHANGE",
        team_id=_attackers(state).club,
        cause=cause,
    )
    return _Change(seq=seq, event=event)


def _carry(state: MatchState, emit: _Emitter, rng: random.Random, pressure: float) -> Step:
    attackers, defenders = _attackers(state), _defenders(state)
    forward = rng.uniform(0.03, 0.12)
    end_progress = min(state.progress + forward, 0.97)
    end_lateral = min(max(state.lateral + rng.uniform(-0.08, 0.08), 0.02), 0.98)
    seq = state.seq + 1
    carry = CarryEvent(
        **emit.envelope(state, seq),
        type="CARRY",
        team_id=attackers.club,
        player_id=state.carrier.player_id,
        origin=_point(state, state.progress, state.lateral, home=state.home_in_possession),
        end=_point(state, end_progress, end_lateral, home=state.home_in_possession),
    )
    state = _advance(replace(state, seq=seq), 1.5 + forward * 20, attackers.style)
    if rng.random() >= 0.18 + 0.35 * pressure:
        return replace(state, progress=end_progress, lateral=end_lateral), [carry]
    # Challenged on the carry.
    tackler = _pick(defenders.on_pitch, zone_of(1 - end_progress, 1 - end_lateral), rng)
    won = rng.random() < 0.55
    seq = state.seq + 1
    tackle = TackleEvent(
        **emit.envelope(state, seq),
        type="TACKLE",
        team_id=defenders.club,
        player_id=tackler.player_id,
        at=_point(state, end_progress, end_lateral, home=state.home_in_possession),
        opponent_id=state.carrier.player_id,
        outcome="won" if won else "lost",
    )
    state = replace(state, seq=seq, progress=end_progress, lateral=end_lateral)
    if not won:
        return state, [carry, tackle]
    state = _turnover(state, tackler, end_progress, end_lateral)
    change = _possession_change(state, emit, "tackle")
    return replace(state, seq=change.seq), [carry, tackle, change.event]


def _shot_position(distance_m: float, lateral: float) -> tuple[float, float]:
    """A point `distance_m` from the centre of goal, keeping the carrier's side of the pitch."""
    sideways_m = (lateral - 0.5) * 68 * 0.6
    sideways_m = max(-0.8 * distance_m, min(0.8 * distance_m, sideways_m))
    depth_m = (distance_m**2 - sideways_m**2) ** 0.5
    return 1.0 - depth_m / 105, 0.5 + sideways_m / 68


def _shot_outcome(xg: float, rng: random.Random) -> ShotOutcome:
    if rng.random() < xg:
        return "goal"
    if rng.random() < SHOT_ON_TARGET_GIVEN_MISS:
        return "saved"
    if rng.random() < BLOCKED_GIVEN_OFF_TARGET:
        return "blocked"
    return "woodwork" if rng.random() < 0.05 else "off_target"


def _shoot(
    state: MatchState, emit: _Emitter, rng: random.Random, pressure: float, passer: Player | None
) -> Step:
    attackers = _attackers(state)
    in_box = zone_of(state.progress, state.lateral) is Zone.BOX
    header = state.carrier.position is Position.FORWARD and in_box and rng.random() < 0.18
    # Where the shot is actually struck: 8-18 m out in the box, 18-30 m from outside it.
    target = rng.triangular(8.0, 18.0, 14.0) if in_box else rng.triangular(18.0, 30.0, 22.0)
    progress, lateral = _shot_position(target, state.lateral)
    state = replace(state, progress=progress, lateral=lateral)
    distance = distance_to_goal(progress, lateral)
    xg = expected_goals(
        distance, shooting_angle(progress, lateral), header=header, pressure=pressure
    )
    outcome = _shot_outcome(xg, rng)
    seq = state.seq + 1
    shot = ShotEvent(
        **emit.envelope(state, seq),
        type="SHOT",
        team_id=attackers.club,
        player_id=state.carrier.player_id,
        origin=_point(state, progress, lateral, home=state.home_in_possession),
        body_part="head" if header else rng.choice(("right_foot", "right_foot", "left_foot")),
        outcome=outcome,
        speed_kmh=round(
            min(170.0, (70 if header else 85) + rng.uniform(0, 40) - distance * 0.3), 1
        ),
        pressure=round(pressure, 3),
    )
    state = replace(state, seq=seq)
    if outcome == "goal":
        state, after = _score_goal(state, emit, rng, shot, passer)
    else:
        state, after = _after_miss(state, emit, rng, shot)
    return state, [shot, *after]


def _score_goal(
    state: MatchState, emit: _Emitter, rng: random.Random, shot: ShotEvent, passer: Player | None
) -> Step:
    attackers = _attackers(state)
    home_scored = state.home_in_possession
    home_score = state.home_score + (1 if home_scored else 0)
    away_score = state.away_score + (0 if home_scored else 1)
    seq = state.seq + 1
    goal = GoalEvent(
        **emit.envelope(state, seq),
        type="GOAL",
        team_id=attackers.club,
        scorer_id=state.carrier.player_id,
        assist_id=passer.player_id if passer and passer != state.carrier else None,
        own_goal=False,
        shot_event_id=shot.event_id,
        score_after=Score(home=home_score, away=away_score),
    )
    state = replace(state, seq=seq, home_score=home_score, away_score=away_score)
    state = _advance(state, 60, attackers.style)
    state = _restart(state, not home_scored, 0.5, 0.5, rng)
    state, kick_off = _set_piece(state, emit, "kick_off", 0.5, 0.5)
    return state, [goal, *kick_off]


def _after_miss(state: MatchState, emit: _Emitter, rng: random.Random, shot: ShotEvent) -> Step:
    attackers, defenders = _attackers(state), _defenders(state)
    events: list[MatchEvent] = []
    state = _advance(state, 6, attackers.style)
    if shot.outcome == "saved":
        seq = state.seq + 1
        events.append(
            SaveEvent(
                **emit.envelope(state, seq),
                type="SAVE",
                team_id=defenders.club,
                player_id=_keeper(defenders).player_id,
                shot_event_id=shot.event_id,
            )
        )
        state = replace(state, seq=seq)
    if shot.outcome in {"saved", "blocked"} and rng.random() < CORNER_GIVEN_BLOCK_OR_SAVE:
        state = _advance(state, 15, attackers.style)
        corner_lateral = 0.0 if rng.random() < 0.5 else 1.0
        state = _restart(state, state.home_in_possession, 1.0, corner_lateral, rng)
        state, corner = _set_piece(state, emit, "corner", 1.0, corner_lateral)
        return state, events + corner
    # Otherwise the defending side restarts from its own box: keeper's ball or goal kick.
    state = _turnover(state, _keeper(defenders), state.progress, state.lateral)
    state = replace(state, progress=0.05, lateral=0.5)
    change = _possession_change(state, emit, "shot_end")
    state = replace(state, seq=change.seq)
    events.append(change.event)
    if shot.outcome in {"off_target", "woodwork"}:
        state, goal_kick = _set_piece(state, emit, "goal_kick", 0.05, 0.5)
        events.extend(goal_kick)
    return state, events


def _substitutions(state: MatchState, emit: _Emitter) -> Step:
    events: list[MatchEvent] = []
    minute = state.elapsed // 60
    for home in (True, False):
        side = _side(state, home)
        while (
            side.sub_minutes
            and side.sub_minutes[0] <= minute
            and side.substitutions < MAX_SUBSTITUTIONS
        ):
            outfield = [p for p in side.on_pitch if p.position is not Position.GOALKEEPER]
            replacements = [b for b in side.bench if b.position is not Position.GOALKEEPER]
            remaining = side.sub_minutes[1:]
            if not outfield or not replacements:
                side = replace(side, sub_minutes=remaining)
                continue
            off = outfield[-1]
            on = next((b for b in replacements if b.position is off.position), replacements[0])
            seq = state.seq + 1
            events.append(
                SubstitutionEvent(
                    **emit.envelope(state, seq),
                    type="SUBSTITUTION",
                    team_id=side.club,
                    player_off_id=off.player_id,
                    player_on_id=on.player_id,
                )
            )
            side = replace(
                side,
                on_pitch=tuple(on if p == off else p for p in side.on_pitch),
                bench=tuple(b for b in side.bench if b != on),
                substitutions=side.substitutions + 1,
                sub_minutes=remaining,
            )
            state = replace(state, seq=seq)
            if state.carrier == off:
                state = replace(state, carrier=on)
        state = _with_side(state, home, side)
    return state, events


def _phase(state: MatchState, emit: _Emitter, rng: random.Random) -> Step:
    # An assist only counts when the shot follows straight from the pass.
    passer = state.last_passer
    state, subs = _substitutions(state, emit)
    state = replace(state, last_passer=None)
    state, pressing, pressure = _press(state, emit, rng)
    if rng.random() < FOUL_RATE * (0.6 + _defenders(state).style.pressing):
        state, foul = _foul(state, emit, rng)
        return state, subs + pressing + foul
    zone = zone_of(state.progress, state.lateral)
    action = choose_action(zone, _attackers(state).style, pressure, rng)
    if action is Action.SHOOT:
        state, shot = _shoot(state, emit, rng, pressure, passer if not pressing else None)
        return state, subs + pressing + shot
    if action is Action.CARRY:
        state, carry = _carry(state, emit, rng, pressure)
        return state, subs + pressing + carry
    state, passing = _pass(state, emit, rng, action, pressure)
    return state, subs + pressing + passing


# --- The match ------------------------------------------------------------------------------------


def _initial_side(team: TeamSetup, rng: random.Random) -> Side:
    xi = starting_xi(team.squad, team.formation)
    bench = tuple(p for p in team.squad.players if p not in xi)
    minutes = tuple(sorted(rng.sample(range(56, 86), MAX_SUBSTITUTIONS)))
    return Side(
        club=team.squad.club, style=team.style, on_pitch=xi, bench=bench, sub_minutes=minutes
    )


def _period_markers(state: MatchState, emit: _Emitter, start: bool) -> Step:
    seq = state.seq + 1
    event: MatchEvent
    if start:
        event = PeriodStartEvent(**emit.envelope(state, seq), type="PERIOD_START")
    else:
        event = PeriodEndEvent(**emit.envelope(state, seq), type="PERIOD_END")
    return replace(state, seq=seq), [event]


def _play_period(
    state: MatchState, emit: _Emitter, rng: random.Random, home_kicks_off: bool
) -> Step:
    state, events = _period_markers(state, emit, start=True)
    state = _restart(state, home_kicks_off, 0.5, 0.5, rng)
    state, kick_off = _set_piece(state, emit, "kick_off", 0.5, 0.5)
    events += kick_off
    while state.elapsed < state.period_end:
        state, phase_events = _phase(state, emit, rng)
        events += phase_events
    state, end = _period_markers(state, emit, start=False)
    return state, events + end


def simulate(setup: MatchSetup) -> tuple[MatchEvent, ...]:
    """Play a whole match and return its events in order. The same setup always gives the same
    events."""
    rng = random.Random(f"{setup.match_id}:{setup.seed}")
    emit = _Emitter(setup)
    home, away = _initial_side(setup.home, rng), _initial_side(setup.away, rng)
    first_added, second_added = rng.randint(1, 4), rng.randint(3, 7)
    home_kicks_off = rng.random() < 0.5
    state = MatchState(
        period=1,
        elapsed=0,
        period_end=HALF_SECONDS + first_added * 60,
        seq=0,
        home=home,
        away=away,
        home_in_possession=home_kicks_off,
        carrier=home.on_pitch[-1],
        progress=0.5,
        lateral=0.5,
    )
    state, first_half = _play_period(state, emit, rng, home_kicks_off)
    state = replace(
        state, period=2, elapsed=HALF_SECONDS, period_end=2 * HALF_SECONDS + second_added * 60
    )
    state, second_half = _play_period(state, emit, rng, not home_kicks_off)
    return tuple(first_half + second_half)
