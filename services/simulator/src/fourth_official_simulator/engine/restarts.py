"""Dead balls: possession changes, restarts, set pieces, and the substitutions made at them."""

import random
from collections.abc import Callable
from dataclasses import replace

from fourth_official_contracts import (
    MatchEvent,
    PossessionChangeEvent,
    SetPieceEvent,
    SubstitutionEvent,
)
from fourth_official_simulator.engine.state import (
    Emitter,
    Envelope,
    MatchState,
    PossessionCause,
    SetPieceKind,
    Side,
    Step,
    keeper,
    pick,
    point,
    side,
    with_side,
)
from fourth_official_simulator.pitch import zone_of
from fourth_official_simulator.squads import Player, Position

MAX_SUBSTITUTIONS = 3
# Forwards are replaced most often, defenders least.
SUBSTITUTION_WEIGHT = {Position.FORWARD: 3.0, Position.MIDFIELDER: 2.0, Position.DEFENDER: 1.0}


def change_possession(
    state: MatchState,
    emit: Emitter,
    cause: PossessionCause,
    *,
    carrier: Player,
    progress: float,
    lateral: float,
) -> Step:
    """Hand the ball to the other side. The only way possession ever changes."""
    state = replace(
        state,
        home_in_possession=not state.home_in_possession,
        carrier=carrier,
        progress=progress,
        lateral=lateral,
        last_passer=None,
        last_delivery=None,
    )
    team = side(state, state.home_in_possession).club
    state, event = emit.stamp(
        state,
        lambda env: PossessionChangeEvent(
            **env, type="POSSESSION_CHANGE", team_id=team, cause=cause
        ),
    )
    return state, [event]


def _substitution(club: str, off: Player, on: Player) -> Callable[[Envelope], SubstitutionEvent]:
    def build(env: Envelope) -> SubstitutionEvent:
        return SubstitutionEvent(
            **env,
            type="SUBSTITUTION",
            team_id=club,
            player_off_id=off.player_id,
            player_on_id=on.player_id,
        )

    return build


def _substitute(state: MatchState, emit: Emitter, rng: random.Random, home: bool) -> Step:
    team = side(state, home)
    minute = state.elapsed // 60
    events: list[MatchEvent] = []
    while (
        team.sub_minutes
        and team.sub_minutes[0] <= minute
        and team.substitutions < MAX_SUBSTITUTIONS
    ):
        candidates = [
            p
            for p in team.on_pitch
            if p.position is not Position.GOALKEEPER
            and p.player_id not in team.subbed_on
            and p != state.carrier
        ]
        replacements = [b for b in team.bench if b.position is not Position.GOALKEEPER]
        if not candidates or not replacements:
            team = replace(team, sub_minutes=team.sub_minutes[1:])
            continue
        off = rng.choices(
            candidates, weights=[SUBSTITUTION_WEIGHT[p.position] for p in candidates]
        )[0]
        on = next((b for b in replacements if b.position is off.position), replacements[0])
        state, event = emit.stamp(state, _substitution(team.club, off, on))
        events.append(event)
        team = replace(
            team,
            on_pitch=tuple(on if p == off else p for p in team.on_pitch),
            bench=tuple(b for b in team.bench if b != on),
            subbed_on=team.subbed_on | {on.player_id},
            substitutions=team.substitutions + 1,
            sub_minutes=team.sub_minutes[1:],
        )
    return with_side(state, home, team), events


def substitutions(state: MatchState, emit: Emitter, rng: random.Random) -> Step:
    """Make any substitutions that are due. Only called at dead balls."""
    state, home_subs = _substitute(state, emit, rng, home=True)
    state, away_subs = _substitute(state, emit, rng, home=False)
    return state, home_subs + away_subs


def set_piece(state: MatchState, emit: Emitter, rng: random.Random, kind: SetPieceKind) -> Step:
    """The ball is dead: substitutions due now are made, then the carrier takes the set piece."""
    state, subs = substitutions(state, emit, rng)
    # A set piece starts a new move: no earlier pass can assist from here.
    state = replace(state, last_passer=None, last_delivery=None)
    team = side(state, state.home_in_possession).club
    taker = state.carrier.player_id
    at = point(state, state.progress, state.lateral)
    state, event = emit.stamp(
        state,
        lambda env: SetPieceEvent(
            **env, type="SET_PIECE", team_id=team, player_id=taker, kind=kind, at=at
        ),
    )
    return state, [*subs, event]


def restart(  # noqa: PLR0913 - every argument is a named part of the restart
    state: MatchState,
    emit: Emitter,
    rng: random.Random,
    kind: SetPieceKind,
    *,
    home_in_possession: bool,
    progress: float,
    lateral: float,
    cause: PossessionCause = "other",
) -> Step:
    """Restart play with a set piece for one side, handing over possession if needed."""
    taking_side: Side = side(state, home_in_possession)
    taker = (
        keeper(taking_side)
        if kind == "goal_kick"
        else pick(taking_side.on_pitch, zone_of(progress, lateral), rng, keepers=False)
    )
    events = []
    if home_in_possession != state.home_in_possession:
        state, change = change_possession(
            state, emit, cause, carrier=taker, progress=progress, lateral=lateral
        )
        events.extend(change)
    else:
        state = replace(
            state,
            carrier=taker,
            progress=progress,
            lateral=lateral,
            last_passer=None,
            last_delivery=None,
        )
    state, taken = set_piece(state, emit, rng, kind)
    return state, [*events, *taken]
