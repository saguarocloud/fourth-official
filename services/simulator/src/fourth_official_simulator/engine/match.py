"""Play a whole match: two halves of phases, with kick-offs, added time and half-time."""

import random
from dataclasses import dataclass, replace

from fourth_official_contracts import (
    Correction,
    GroundTruth,
    MatchEvent,
    PeriodEndEvent,
    PeriodStartEvent,
    Score,
)
from fourth_official_simulator.engine.actions import carry, foul, foul_rate, pass_ball, press, shoot
from fourth_official_simulator.engine.restarts import MAX_SUBSTITUTIONS, restart, set_piece
from fourth_official_simulator.engine.scripted import (
    apply_styles,
    due_moment,
    play_moment,
    reassign_scorers,
)
from fourth_official_simulator.engine.state import (
    HALF_SECONDS,
    Emitter,
    MatchSetup,
    MatchState,
    Side,
    Step,
    TeamSetup,
    attackers,
    pick,
    side,
)
from fourth_official_simulator.pitch import Zone, zone_of
from fourth_official_simulator.probabilities import Action, choose_action
from fourth_official_simulator.squads import starting_xi

# Windows for planned substitutions and added time, in minutes.
SUBSTITUTION_WINDOW = range(56, 86)
FIRST_HALF_ADDED = (1, 4)
SECOND_HALF_ADDED = (3, 7)


def _phase(state: MatchState, emit: Emitter, rng: random.Random) -> Step:
    # The last completed pass to the carrier in this move assists a goal, even if the carrier was
    # pressed or dribbled first.
    passer = state.last_passer
    state, pressing, pressure = press(state, emit, rng)
    if rng.random() < foul_rate(state):
        state, fouled = foul(state, emit, rng)
        return state, [*pressing, *fouled]
    action = choose_action(
        zone_of(state.progress, state.lateral), attackers(state).style, pressure, rng
    )
    if action is Action.SHOOT:
        state, played = shoot(state, emit, rng, pressure=pressure, passer=passer)
    elif action is Action.CARRY:
        state, played = carry(state, emit, rng, pressure=pressure)
    else:
        state, played = pass_ball(state, emit, rng, action=action, pressure=pressure)
    return state, [*pressing, *played]


def _initial_side(team: TeamSetup, rng: random.Random) -> Side:
    xi = starting_xi(team.squad, team.formation)
    bench = tuple(p for p in team.squad.players if p not in xi)
    minutes = tuple(sorted(rng.sample(SUBSTITUTION_WINDOW, MAX_SUBSTITUTIONS)))
    return Side(
        club=team.squad.club, style=team.style, on_pitch=xi, bench=bench, sub_minutes=minutes
    )


def _play_period(
    state: MatchState, emit: Emitter, rng: random.Random, home_kicks_off: bool
) -> Step:
    state, started = emit.stamp(state, lambda env: PeriodStartEvent(**env, type="PERIOD_START"))
    events: list[MatchEvent] = [started]
    if home_kicks_off == state.home_in_possession:
        taker = pick(side(state, home_kicks_off).on_pitch, Zone.MIDDLE_THIRD, rng, keepers=False)
        state = replace(
            state, carrier=taker, progress=0.5, lateral=0.5, last_passer=None, last_delivery=None
        )
        state, kick_off = set_piece(state, emit, rng, "kick_off")
    else:
        state, kick_off = restart(
            state,
            emit,
            rng,
            "kick_off",
            home_in_possession=home_kicks_off,
            progress=0.5,
            lateral=0.5,
        )
    events += kick_off
    story = emit.setup.storyline
    while state.elapsed < state.period_end:
        if story is not None:
            state = apply_styles(state, emit, story)
            due = due_moment(state, story)
            if due is not None:
                state, played = play_moment(state, emit, rng, story=story, due=due)
                events += played
                continue
        state, played = _phase(state, emit, rng)
        events += played
    state, ended = emit.stamp(state, lambda env: PeriodEndEvent(**env, type="PERIOD_END"))
    return state, [*events, ended]


@dataclass(frozen=True, slots=True)
class SimulatedMatch:
    """A played match: its events in order, the corrections issued later, and what really
    happened."""

    events: tuple[MatchEvent, ...]
    corrections: tuple[Correction, ...]
    ground_truth: GroundTruth


def _check_storyline(setup: MatchSetup) -> None:
    clubs = {setup.home.squad.club, setup.away.squad.club}
    if setup.storyline is not None and not setup.storyline.clubs() <= clubs:
        unknown = sorted(setup.storyline.clubs() - clubs)
        raise ValueError(f"storyline names clubs not in the match: {', '.join(unknown)}")


def play(setup: MatchSetup) -> SimulatedMatch:
    """Play a whole match, storyline included. The same setup always gives the same match, in any
    process."""
    _check_storyline(setup)
    rng = random.Random(f"{setup.match_id}:{setup.seed}")
    emit = Emitter(setup)
    home, away = _initial_side(setup.home, rng), _initial_side(setup.away, rng)
    first_added, second_added = rng.randint(*FIRST_HALF_ADDED), rng.randint(*SECOND_HALF_ADDED)
    home_kicks_off = rng.random() < 0.5
    state = MatchState(
        period=1,
        elapsed=0,
        period_end=HALF_SECONDS + first_added * 60,
        seq=0,
        home=home,
        away=away,
        home_in_possession=home_kicks_off,
        carrier=(home if home_kicks_off else away).on_pitch[-1],
        progress=0.5,
        lateral=0.5,
    )
    state, first_half = _play_period(state, emit, rng, home_kicks_off)
    state = replace(
        state,
        period=2,
        first_half_end=state.elapsed,
        elapsed=HALF_SECONDS,
        period_end=2 * HALF_SECONDS + second_added * 60,
    )
    state, second_half = _play_period(state, emit, rng, not home_kicks_off)
    events = tuple(first_half + second_half)
    log = state.story
    if setup.storyline is not None:
        log = reassign_scorers(log, rng, story=setup.storyline, final_whistle=events[-1])
    truth = GroundTruth(
        match_id=setup.match_id,
        seed=setup.seed,
        storyline=setup.storyline.name if setup.storyline else "No storyline",
        home=setup.home.squad.club,
        away=setup.away.squad.club,
        final_score=Score(home=state.home_score, away=state.away_score),
        storylines=log.truths,
    )
    return SimulatedMatch(events=events, corrections=log.corrections, ground_truth=truth)


def simulate(setup: MatchSetup) -> tuple[MatchEvent, ...]:
    """Play a whole match and return its events in order. The same setup always gives the same
    events, in any process."""
    return play(setup).events
