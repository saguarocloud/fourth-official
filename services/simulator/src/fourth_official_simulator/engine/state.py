"""Setups, the frozen match state, and the emitter that stamps every new event."""

import random
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal, TypedDict

from fourth_official_contracts import (
    Correction,
    EventEnvelope,
    GoalEvent,
    MatchClock,
    MatchEvent,
    PitchPoint,
    StorylineTruth,
)
from fourth_official_simulator.pitch import Zone, attacking_to_pitch
from fourth_official_simulator.squads import Player, Position, Squad
from fourth_official_simulator.storylines import ScriptedGoal, Storyline
from fourth_official_simulator.style import TeamStyle

HALF_SECONDS = 45 * 60
HALF_TIME_BREAK = timedelta(minutes=15)

Period = Literal[1, 2]
SetPieceKind = Literal["kick_off", "corner", "free_kick", "throw_in", "goal_kick", "penalty"]
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
    storyline: Storyline | None = None


@dataclass(frozen=True, slots=True)
class ScoredGoal:
    """A scripted goal as it happened, and the scoring side's outfield players at the time."""

    directive: ScriptedGoal
    event: GoalEvent
    on_pitch: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoryLog:
    """What the storyline has done so far: moments played, and the record it leaves behind."""

    moments_done: frozenset[int] = frozenset()
    shifts_seen: frozenset[int] = frozenset()
    goals: tuple[ScoredGoal, ...] = ()
    corrections: tuple[Correction, ...] = ()
    truths: tuple[StorylineTruth, ...] = ()


@dataclass(frozen=True, slots=True)
class Side:
    """One team's in-match situation."""

    club: str
    style: TeamStyle
    on_pitch: tuple[Player, ...]
    bench: tuple[Player, ...]
    booked: frozenset[str] = frozenset()
    subbed_on: frozenset[str] = frozenset()
    substitutions: int = 0
    # Minutes from which each planned substitution may happen, at the next dead ball.
    sub_minutes: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchState:
    period: Period
    elapsed: int  # seconds on the match clock (the second half starts at 45:00)
    period_end: int  # seconds at which the current period ends, including added time
    seq: int
    home: Side
    away: Side
    home_in_possession: bool
    carrier: Player
    progress: float  # attacking frame: 0 = own goal line, 1 = opponent goal line
    lateral: float
    home_score: int = 0
    away_score: int = 0
    # Second at which the first half ended (added time included); fixes the second-half wall clock.
    first_half_end: int = HALF_SECONDS
    # The player whose completed pass reached the carrier, and that pass's kind, if the carrier has
    # not yet acted.
    last_passer: Player | None = None
    last_delivery: str | None = None  # the kind of that pass (a cross sets up headers)
    # Whether the carrier has already dribbled since receiving; a second dribble ends the assist.
    dribbled: bool = False
    story: StoryLog = StoryLog()


class Envelope(TypedDict):
    event_id: str
    match_id: str
    seq: int
    version: int
    clock: MatchClock
    wall_clock: datetime


@dataclass(frozen=True, slots=True)
class Emitter:
    """Numbers, identifies and timestamps each new event."""

    setup: MatchSetup

    def _envelope(self, state: MatchState, seq: int) -> Envelope:
        minute, second = divmod(state.elapsed, 60)
        if state.period == 1:
            wall = self.setup.kickoff + timedelta(seconds=state.elapsed)
        else:
            wall = (
                self.setup.kickoff
                + timedelta(seconds=state.first_half_end)
                + HALF_TIME_BREAK
                + timedelta(seconds=state.elapsed - HALF_SECONDS)
            )
        return {
            "event_id": f"{self.setup.match_id}-e{seq:04d}",
            "match_id": self.setup.match_id,
            "seq": seq,
            "version": 1,
            "clock": MatchClock(period=state.period, minute=minute, second=second),
            "wall_clock": wall,
        }

    def stamp[E: EventEnvelope](
        self, state: MatchState, build: Callable[[Envelope], E]
    ) -> tuple[MatchState, E]:
        """Create the next event from its envelope and advance the sequence."""
        seq = state.seq + 1
        return replace(state, seq=seq), build(self._envelope(state, seq))


Step = tuple[MatchState, list[MatchEvent]]


def natural_goals(emit: Emitter) -> bool:
    """Whether goals other than the storyline's scripted ones may happen."""
    story = emit.setup.storyline
    return story is None or story.natural_goals


def wait(state: MatchState, seconds: int) -> MatchState:
    """Let time pass at a stoppage (VAR, a scripted lull), whatever the tempo."""
    return replace(state, elapsed=min(state.elapsed + seconds, state.period_end))


# How likely each position is to be involved on the ball in each zone.
ROLE_WEIGHTS: dict[Zone, dict[Position, float]] = {
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


def side(state: MatchState, home: bool) -> Side:
    return state.home if home else state.away


def attackers(state: MatchState) -> Side:
    return side(state, state.home_in_possession)


def defenders(state: MatchState) -> Side:
    return side(state, not state.home_in_possession)


def with_side(state: MatchState, home: bool, team: Side) -> MatchState:
    return replace(state, home=team) if home else replace(state, away=team)


def point(state: MatchState, progress: float, lateral: float) -> PitchPoint:
    """A point in the attacking frame of the team in possession, as pitch metres."""
    x, y = attacking_to_pitch(progress, lateral, home=state.home_in_possession, period=state.period)
    return PitchPoint(x=x, y=y)


def pick(
    players: tuple[Player, ...],
    zone: Zone,
    rng: random.Random,
    *,
    exclude: Player | None = None,
    keepers: bool = True,
) -> Player:
    """A player likely to be involved in this zone (outfield only unless `keepers`)."""
    candidates = [
        p for p in players if p != exclude and (keepers or p.position is not Position.GOALKEEPER)
    ] or list(players)
    weights = [ROLE_WEIGHTS[zone][p.position] + 0.05 for p in candidates]
    return rng.choices(candidates, weights=weights)[0]


def keeper(team: Side) -> Player:
    keepers = [p for p in team.on_pitch if p.position is Position.GOALKEEPER]
    return keepers[0] if keepers else team.on_pitch[0]


def advance(state: MatchState, seconds: float) -> MatchState:
    """Let time pass; higher tempo makes phases quicker."""
    duration = max(1, round(seconds * (1.35 - 0.6 * attackers(state).style.tempo)))
    return replace(state, elapsed=min(state.elapsed + duration, state.period_end))
