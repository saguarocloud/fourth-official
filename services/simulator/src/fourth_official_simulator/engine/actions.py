"""What happens on the ball in one phase: pressing, fouls and penalties, passes, carries, shots."""

import math
import random
from dataclasses import dataclass, replace
from typing import Literal

from fourth_official_contracts import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    CardEvent,
    CarryEvent,
    FoulEvent,
    GoalEvent,
    InterceptionEvent,
    MatchEvent,
    OffsideEvent,
    PassEvent,
    PressureEvent,
    SaveEvent,
    Score,
    ShotEvent,
    TackleEvent,
)
from fourth_official_simulator.engine.restarts import change_possession, restart, set_piece
from fourth_official_simulator.engine.state import (
    Emitter,
    MatchState,
    Step,
    advance,
    attackers,
    defenders,
    keeper,
    natural_goals,
    pick,
    point,
    with_side,
)
from fourth_official_simulator.pitch import Zone, distance_to_goal, shooting_angle, zone_of
from fourth_official_simulator.probabilities import (
    Action,
    PassKind,
    expected_goals,
    pass_completion,
)
from fourth_official_simulator.squads import Player, Position

ShotOutcome = Literal["goal", "saved", "off_target", "blocked", "woodwork"]
BodyPart = Literal["right_foot", "left_foot", "head", "other"]
CardKind = Literal["yellow", "second_yellow", "red"]

# --- Rates and geometry (tuned so whole matches land in public aggregate ranges) ------------------
PRESS_RATE = 0.55
FOUL_RATE = 0.018
YELLOW_GIVEN_FOUL = 0.17
RED_GIVEN_FOUL = 0.002
# Booked players foul far less often.
BOOKED_FOUL_WEIGHT = 0.3
# Defenders rarely risk a foul in their own box: about 0.3 penalties per match.
FOUL_RATE_IN_BOX = 0.08
OFFSIDE_GIVEN_THROUGH_BALL = 0.045
OUT_OF_PLAY_GIVEN_MISS = 0.35
GOAL_KICK_GIVEN_LONG_MISS_NEAR_GOAL = 0.5
SWITCH_SHARE_OF_LONG_PASSES = 0.3
CARRY_CHALLENGE_BASE = 0.18
CARRY_CHALLENGE_PER_PRESSURE = 0.35
TACKLE_WIN_RATE = 0.55
SHOT_ON_TARGET_GIVEN_MISS = 0.3
BLOCKED_GIVEN_OFF_TARGET = 0.3
WOODWORK_GIVEN_OFF_TARGET = 0.05
CORNER_GIVEN_BLOCK_OR_SAVE = 0.4
HEADER_AFTER_CROSS = 0.55
HEADER_OTHERWISE_IN_BOX = 0.06
# Penalties convert at roughly three in four in public aggregates.
PENALTY_GOAL = 0.76
PENALTY_SAVED = 0.17
PENALTY_SPOT = 1.0 - 11.0 / PITCH_LENGTH_M
# Open play rarely carries the ball closer than about 8 m from goal; crosses reach 5-12 m.
MAX_PROGRESS = 0.92
# Near goal, play goes sideways and back (cut-backs, lay-offs) rather than straight on.
NEAR_GOAL = 0.8


# --- Pressing and fouls ---------------------------------------------------------------------------


def press(
    state: MatchState, emit: Emitter, rng: random.Random
) -> tuple[MatchState, list[MatchEvent], float]:
    """The defending side may press the carrier; returns the pressure the carrier is under."""
    pressers = defenders(state)
    zone = zone_of(state.progress, state.lateral)
    # Pressing is fiercest high up the pitch, i.e. in the carrier's own third.
    height = 1.3 if zone is Zone.DEFENSIVE_THIRD else 1.0 if zone is Zone.MIDDLE_THIRD else 0.8
    if rng.random() >= PRESS_RATE * pressers.style.pressing * height:
        # Even unpressed, a player in the box has defenders close by.
        ambient = rng.uniform(0.2, 0.5) if zone is Zone.BOX else rng.uniform(0.0, 0.25)
        return state, [], ambient
    intensity = round(min(1.0, rng.uniform(0.3, 1.0) * (0.6 + 0.6 * pressers.style.pressing)), 3)
    presser = pick(
        pressers.on_pitch,
        Zone.FINAL_THIRD if zone is Zone.DEFENSIVE_THIRD else Zone.MIDDLE_THIRD,
        rng,
    )
    at = point(state, state.progress, state.lateral)
    target = state.carrier.player_id
    state, event = emit.stamp(
        state,
        lambda env: PressureEvent(
            **env,
            type="PRESSURE",
            team_id=pressers.club,
            player_id=presser.player_id,
            at=at,
            target_id=target,
            intensity=intensity,
        ),
    )
    return state, [event], intensity


def foul_rate(state: MatchState) -> float:
    rate = FOUL_RATE * (0.6 + defenders(state).style.pressing)
    return rate * FOUL_RATE_IN_BOX if zone_of(state.progress, state.lateral) is Zone.BOX else rate


def _offender(
    team_players: tuple[Player, ...], booked: frozenset[str], rng: random.Random
) -> Player:
    outfield = [p for p in team_players if p.position is not Position.GOALKEEPER]
    weights = [BOOKED_FOUL_WEIGHT if p.player_id in booked else 1.0 for p in outfield]
    return rng.choices(outfield, weights=weights)[0]


def _card_for(offender: Player, booked: frozenset[str], roll: float) -> CardKind | None:
    if roll < RED_GIVEN_FOUL:
        return "red"
    if roll < RED_GIVEN_FOUL + YELLOW_GIVEN_FOUL:
        return "second_yellow" if offender.player_id in booked else "yellow"
    return None


def foul(
    state: MatchState, emit: Emitter, rng: random.Random, *, card: CardKind | None = None
) -> Step:
    """The carrier is fouled: maybe a card (always `card`, if given), then a free kick, or a
    penalty inside the box."""
    team = defenders(state)
    offender = _offender(team.on_pitch, team.booked, rng)
    at = point(state, state.progress, state.lateral)
    victim = state.carrier.player_id
    state, committed = emit.stamp(
        state,
        lambda env: FoulEvent(
            **env,
            type="FOUL",
            team_id=team.club,
            player_id=offender.player_id,
            at=at,
            victim_id=victim,
        ),
    )
    events: list[MatchEvent] = [committed]
    card = card or _card_for(offender, team.booked, rng.random())
    if card is not None:
        state, shown = emit.stamp(
            state,
            lambda env: CardEvent(
                **env,
                type="CARD",
                team_id=team.club,
                player_id=offender.player_id,
                card=card,
                foul_event_id=committed.event_id,
            ),
        )
        events.append(shown)
        team = (
            replace(team, booked=team.booked | {offender.player_id})
            if card == "yellow"
            else replace(team, on_pitch=tuple(p for p in team.on_pitch if p != offender))
        )
        state = with_side(state, not state.home_in_possession, team)
    state = advance(state, rng.uniform(25, 45))
    if zone_of(state.progress, state.lateral) is Zone.BOX:
        state, awarded = restart(
            state,
            emit,
            rng,
            "penalty",
            home_in_possession=state.home_in_possession,
            progress=PENALTY_SPOT,
            lateral=0.5,
        )
        state, kick = penalty_kick(state, emit, rng)
        return state, [*events, *awarded, *kick]
    state, free_kick = set_piece(state, emit, rng, "free_kick")
    return state, [*events, *free_kick]


# --- Passing --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _PassPlan:
    kind: PassKind
    end_progress: float
    end_lateral: float
    distance_m: float


def _plan_pass(state: MatchState, action: Action, rng: random.Random) -> _PassPlan:
    style = attackers(state).style
    kind: PassKind
    if action is Action.LONG_PASS:
        kind = "switch" if rng.random() < SWITCH_SHARE_OF_LONG_PASSES else "lofted"
        end = (state.progress + rng.uniform(0.18, 0.4), state.lateral + rng.uniform(-0.45, 0.45))
    elif action is Action.THROUGH_BALL:
        kind = "through"
        end = (state.progress + rng.uniform(0.12, 0.28), state.lateral + rng.uniform(-0.15, 0.15))
    elif action is Action.CROSS:
        kind = "cross"
        end = (rng.uniform(0.88, 0.95), rng.uniform(0.35, 0.65))
    else:
        kind = "ground"
        if state.progress >= NEAR_GOAL:
            forward = rng.uniform(-0.1, 0.05)
        else:
            forward = rng.uniform(-0.06, 0.16) + 0.06 * style.directness
        end = (
            state.progress + forward,
            state.lateral + rng.uniform(-0.2, 0.2) * (0.5 + style.width),
        )
    end_progress = min(max(end[0], 0.02), MAX_PROGRESS)
    end_lateral = min(max(end[1], 0.02), 0.98)
    distance = math.hypot(
        (end_progress - state.progress) * PITCH_LENGTH_M,
        (end_lateral - state.lateral) * PITCH_WIDTH_M,
    )
    return _PassPlan(kind, end_progress, end_lateral, distance)


def pass_ball(
    state: MatchState, emit: Emitter, rng: random.Random, *, action: Action, pressure: float
) -> Step:
    plan = _plan_pass(state, action, rng)
    completed = rng.random() < pass_completion(plan.distance_m, pressure, kind=plan.kind)
    if completed and plan.kind == "through" and rng.random() < OFFSIDE_GIVEN_THROUGH_BALL:
        return _offside(state, emit, rng, plan)
    team = attackers(state)
    receiver = (
        pick(
            team.on_pitch, zone_of(plan.end_progress, plan.end_lateral), rng, exclude=state.carrier
        )
        if completed
        else None
    )
    origin, end = (
        point(state, state.progress, state.lateral),
        point(state, plan.end_progress, plan.end_lateral),
    )
    passer = state.carrier
    speed = round(min(140.0, 30 + plan.distance_m * 1.4 + rng.uniform(-5, 5)), 1)
    state, made = emit.stamp(
        state,
        lambda env: PassEvent(
            **env,
            type="PASS",
            team_id=team.club,
            player_id=passer.player_id,
            origin=origin,
            end=end,
            outcome="complete" if completed else "incomplete",
            receiver_id=receiver.player_id if receiver else None,
            kind=plan.kind,
            speed_kmh=speed,
        ),
    )
    state = advance(state, 2.2 + plan.distance_m / 16)
    if receiver is not None:
        moved = replace(
            state,
            carrier=receiver,
            progress=plan.end_progress,
            lateral=plan.end_lateral,
            last_passer=passer,
            last_delivery=plan.kind,
            dribbled=False,
        )
        return moved, [made]
    if rng.random() < OUT_OF_PLAY_GIVEN_MISS:
        state, restarted = _out_of_play(state, emit, rng, plan)
    else:
        state, restarted = _intercepted(state, emit, rng, plan)
    return state, [made, *restarted]


def _offside(state: MatchState, emit: Emitter, rng: random.Random, plan: _PassPlan) -> Step:
    team = attackers(state)
    runner = pick(team.on_pitch, Zone.FINAL_THIRD, rng, exclude=state.carrier, keepers=False)
    at = point(state, plan.end_progress, plan.end_lateral)
    state, flagged = emit.stamp(
        state,
        lambda env: OffsideEvent(
            **env, type="OFFSIDE", team_id=team.club, player_id=runner.player_id, at=at
        ),
    )
    state = advance(state, 20)
    state, free_kick = restart(
        state,
        emit,
        rng,
        "free_kick",
        home_in_possession=not state.home_in_possession,
        progress=1.0 - plan.end_progress,
        lateral=1.0 - plan.end_lateral,
    )
    return state, [flagged, *free_kick]


def _out_of_play(state: MatchState, emit: Emitter, rng: random.Random, plan: _PassPlan) -> Step:
    state = advance(state, 12)
    over_goal_line = plan.kind in {"lofted", "through", "switch"} and plan.end_progress >= 0.93
    if over_goal_line and rng.random() < GOAL_KICK_GIVEN_LONG_MISS_NEAR_GOAL:
        return restart(
            state,
            emit,
            rng,
            "goal_kick",
            home_in_possession=not state.home_in_possession,
            progress=0.05,
            lateral=0.5,
            cause="out_of_play",
        )
    touchline = 0.0 if plan.end_lateral < 0.5 else 1.0
    return restart(
        state,
        emit,
        rng,
        "throw_in",
        home_in_possession=not state.home_in_possession,
        progress=1.0 - plan.end_progress,
        lateral=1.0 - touchline,
        cause="out_of_play",
    )


def _intercepted(state: MatchState, emit: Emitter, rng: random.Random, plan: _PassPlan) -> Step:
    progress, lateral = 1.0 - plan.end_progress, 1.0 - plan.end_lateral
    interceptor = pick(defenders(state).on_pitch, zone_of(progress, lateral), rng)
    team = defenders(state).club
    state, changed = change_possession(
        state, emit, "interception", carrier=interceptor, progress=progress, lateral=lateral
    )
    # The interception is recorded after the change, in the new possessor's frame.
    at = point(state, progress, lateral)
    state, cut_out = emit.stamp(
        state,
        lambda env: InterceptionEvent(
            **env, type="INTERCEPTION", team_id=team, player_id=interceptor.player_id, at=at
        ),
    )
    return state, [*changed, cut_out]


# --- Carrying -------------------------------------------------------------------------------------


def carry(state: MatchState, emit: Emitter, rng: random.Random, *, pressure: float) -> Step:
    team = attackers(state)
    forward = rng.uniform(0.0, 0.04) if state.progress >= NEAR_GOAL else rng.uniform(0.03, 0.12)
    end_progress = min(state.progress + forward, max(state.progress, MAX_PROGRESS))
    end_lateral = min(max(state.lateral + rng.uniform(-0.08, 0.08), 0.02), 0.98)
    origin, end = (
        point(state, state.progress, state.lateral),
        point(state, end_progress, end_lateral),
    )
    runner = state.carrier.player_id
    state, carried = emit.stamp(
        state,
        lambda env: CarryEvent(
            **env, type="CARRY", team_id=team.club, player_id=runner, origin=origin, end=end
        ),
    )
    # One dribble keeps the assist alive (the passer still set the goal up); a second ends it.
    state = replace(
        advance(state, 1.5 + forward * 20),
        progress=end_progress,
        lateral=end_lateral,
        last_delivery=None,
        last_passer=None if state.dribbled else state.last_passer,
        dribbled=True,
    )
    if rng.random() >= CARRY_CHALLENGE_BASE + CARRY_CHALLENGE_PER_PRESSURE * pressure:
        return state, [carried]
    return _challenge(state, emit, rng, carried)


def _challenge(state: MatchState, emit: Emitter, rng: random.Random, carried: CarryEvent) -> Step:
    opposition = defenders(state)
    tackler = pick(
        opposition.on_pitch, zone_of(1 - state.progress, 1 - state.lateral), rng, keepers=False
    )
    won = rng.random() < TACKLE_WIN_RATE
    at = point(state, state.progress, state.lateral)
    beaten = state.carrier.player_id
    state, tackled = emit.stamp(
        state,
        lambda env: TackleEvent(
            **env,
            type="TACKLE",
            team_id=opposition.club,
            player_id=tackler.player_id,
            at=at,
            opponent_id=beaten,
            outcome="won" if won else "lost",
        ),
    )
    if not won:
        return state, [carried, tackled]
    state, changed = change_possession(
        state,
        emit,
        "tackle",
        carrier=tackler,
        progress=1 - state.progress,
        lateral=1 - state.lateral,
    )
    return state, [carried, tackled, *changed]


# --- Shooting -------------------------------------------------------------------------------------


def _open_play_outcome(xg: float, rng: random.Random) -> ShotOutcome:
    if rng.random() < xg:
        return "goal"
    if rng.random() < SHOT_ON_TARGET_GIVEN_MISS:
        return "saved"
    if rng.random() < BLOCKED_GIVEN_OFF_TARGET:
        return "blocked"
    return "woodwork" if rng.random() < WOODWORK_GIVEN_OFF_TARGET else "off_target"


def shoot(
    state: MatchState, emit: Emitter, rng: random.Random, *, pressure: float, passer: Player | None
) -> Step:
    """A shot from where the carrier is. Headers mostly follow crosses."""
    in_box = zone_of(state.progress, state.lateral) is Zone.BOX
    header_chance = (
        HEADER_AFTER_CROSS
        if state.last_delivery == "cross"
        else HEADER_OTHERWISE_IN_BOX
        if in_box
        else 0.0
    )
    header = rng.random() < header_chance
    distance = distance_to_goal(state.progress, state.lateral)
    xg = expected_goals(
        distance, shooting_angle(state.progress, state.lateral), header=header, pressure=pressure
    )
    outcome = _open_play_outcome(xg, rng)
    foot: BodyPart = rng.choice(("right_foot", "right_foot", "left_foot"))
    speed = round(
        min(170.0, max(40.0, (70 if header else 85) + rng.uniform(0, 40) - distance * 0.3)), 1
    )
    body: BodyPart = "head" if header else foot
    return _strike(state, emit, rng, strike=Strike(outcome, body, speed, pressure), passer=passer)


def penalty_kick(state: MatchState, emit: Emitter, rng: random.Random) -> Step:
    roll = rng.random()
    outcome: ShotOutcome = (
        "goal"
        if roll < PENALTY_GOAL
        else "saved"
        if roll < PENALTY_GOAL + PENALTY_SAVED
        else "off_target"
    )
    foot: BodyPart = rng.choice(("right_foot", "left_foot"))
    strike = Strike(outcome, foot, round(rng.uniform(95.0, 125.0), 1), 0.0)
    return _strike(state, emit, rng, strike=strike, passer=None)


@dataclass(frozen=True, slots=True)
class Strike:
    outcome: ShotOutcome
    body_part: BodyPart
    speed: float
    pressure: float


def strike_shot(state: MatchState, emit: Emitter, strike: Strike) -> tuple[MatchState, ShotEvent]:
    """The carrier strikes the ball from where they are."""
    team = attackers(state)
    shooter = state.carrier.player_id
    origin = point(state, state.progress, state.lateral)
    return emit.stamp(
        state,
        lambda env: ShotEvent(
            **env,
            type="SHOT",
            team_id=team.club,
            player_id=shooter,
            origin=origin,
            body_part=strike.body_part,
            outcome=strike.outcome,
            speed_kmh=strike.speed,
            pressure=round(strike.pressure, 3),
        ),
    )


def _strike(
    state: MatchState, emit: Emitter, rng: random.Random, *, strike: Strike, passer: Player | None
) -> Step:
    if strike.outcome == "goal" and not natural_goals(emit):
        strike = replace(strike, outcome="saved")
    state, shot = strike_shot(state, emit, strike)
    if strike.outcome == "goal":
        state, after = _goal(state, emit, rng, shot=shot, passer=passer)
    else:
        state, after = _after_miss(state, emit, rng, shot)
    return state, [shot, *after]


def award_goal(
    state: MatchState, emit: Emitter, *, shot: ShotEvent, passer: Player | None
) -> tuple[MatchState, GoalEvent]:
    """The shot went in: credit the carrier and the passer who set them up; update the score."""
    home_scored = state.home_in_possession
    score = Score(home=state.home_score + home_scored, away=state.away_score + (not home_scored))
    club, scorer = attackers(state).club, state.carrier.player_id
    assist = passer.player_id if passer is not None else None
    state, scored = emit.stamp(
        state,
        lambda env: GoalEvent(
            **env,
            type="GOAL",
            team_id=club,
            scorer_id=scorer,
            assist_id=assist,
            own_goal=False,
            shot_event_id=shot.event_id,
            score_after=score,
        ),
    )
    return replace(state, home_score=score.home, away_score=score.away), scored


def kick_off_after_goal(
    state: MatchState, emit: Emitter, rng: random.Random, *, home_scored: bool
) -> Step:
    state = advance(state, 60)
    return restart(
        state, emit, rng, "kick_off", home_in_possession=not home_scored, progress=0.5, lateral=0.5
    )


def _goal(
    state: MatchState, emit: Emitter, rng: random.Random, *, shot: ShotEvent, passer: Player | None
) -> Step:
    home_scored = state.home_in_possession
    state, scored = award_goal(state, emit, shot=shot, passer=passer)
    state, kick_off = kick_off_after_goal(state, emit, rng, home_scored=home_scored)
    return state, [scored, *kick_off]


def _after_miss(state: MatchState, emit: Emitter, rng: random.Random, shot: ShotEvent) -> Step:
    events: list[MatchEvent] = []
    state = advance(state, 6)
    opposition = defenders(state)
    if shot.outcome == "saved":
        goalkeeper = keeper(opposition)
        state, save = emit.stamp(
            state,
            lambda env: SaveEvent(
                **env,
                type="SAVE",
                team_id=opposition.club,
                player_id=goalkeeper.player_id,
                shot_event_id=shot.event_id,
            ),
        )
        events.append(save)
    if shot.outcome in {"saved", "blocked"} and rng.random() < CORNER_GIVEN_BLOCK_OR_SAVE:
        state = advance(state, 15)
        flag = 0.0 if rng.random() < 0.5 else 1.0
        state, corner = restart(
            state,
            emit,
            rng,
            "corner",
            home_in_possession=state.home_in_possession,
            progress=1.0,
            lateral=flag,
        )
        return state, [*events, *corner]
    if shot.outcome in {"off_target", "woodwork"}:
        state, goal_kick = restart(
            state,
            emit,
            rng,
            "goal_kick",
            home_in_possession=not state.home_in_possession,
            progress=0.05,
            lateral=0.5,
            cause="shot_end",
        )
        return state, [*events, *goal_kick]
    # The keeper holds the save, or a defender gathers the block.
    if shot.outcome == "saved":
        gatherer, progress, lateral = keeper(opposition), 0.05, 0.5
    else:
        gatherer = pick(opposition.on_pitch, Zone.DEFENSIVE_THIRD, rng, keepers=False)
        progress, lateral = 1 - state.progress, 1 - state.lateral
    state, changed = change_possession(
        state, emit, "shot_end", carrier=gatherer, progress=progress, lateral=lateral
    )
    return state, [*events, *changed]
