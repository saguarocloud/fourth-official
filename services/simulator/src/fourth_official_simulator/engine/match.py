"""Play a whole match: two halves of phases, with kick-offs, added time and half-time."""

import random
from dataclasses import replace

from fourth_official_contracts import MatchEvent, PeriodEndEvent, PeriodStartEvent
from fourth_official_simulator.engine.actions import carry, foul, foul_rate, pass_ball, press, shoot
from fourth_official_simulator.engine.restarts import MAX_SUBSTITUTIONS, restart, set_piece
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
    while state.elapsed < state.period_end:
        state, played = _phase(state, emit, rng)
        events += played
    state, ended = emit.stamp(state, lambda env: PeriodEndEvent(**env, type="PERIOD_END"))
    return state, [*events, ended]


def simulate(setup: MatchSetup) -> tuple[MatchEvent, ...]:
    """Play a whole match and return its events in order. The same setup always gives the same
    events, in any process."""
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
    return tuple(first_half + second_half)
