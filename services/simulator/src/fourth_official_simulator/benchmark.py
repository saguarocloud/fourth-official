"""The Proving Ground's benchmark: a hundred seeded matches, each with a storyline planted in it.

Every match is drawn from its own seed, so the benchmark is the same on every machine and a
smaller run (the CI smoke subset) is the start of the full one. Storylines mix what the pipeline
must handle: goals, red cards, a press that collapses, goals VAR rules out after they are
published, and scorers reassigned after the final whistle. Their ground truth comes from the
simulator itself, as for the demo matchday.
"""

import random
from datetime import UTC, datetime

from fourth_official_simulator.engine import MatchSetup, TeamSetup
from fourth_official_simulator.squads import CLUB_CODES, FORMATIONS, generate_squad
from fourth_official_simulator.storylines import (
    FIRST_MINUTE,
    HALF_TIME_MINUTE,
    LAST_FIRST_HALF_VAR_MINUTE,
    LAST_MINUTE,
    MIN_MINUTES_APART,
    Directive,
    RedCard,
    ScorerReassigned,
    ScriptedGoal,
    Storyline,
    StyleShift,
    VarVoid,
)
from fourth_official_simulator.style import TeamStyle

BENCHMARK_SIZE = 100
FIRST_MATCH_NUMBER = 1001
SQUAD_SEED = 2026
KICKOFF = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)

# How many goals a match is scripted with, and how often (weights, not probabilities).
GOAL_COUNTS = (0, 1, 2, 3, 4)
GOAL_WEIGHTS = (15, 25, 30, 20, 10)
RED_CARD_CHANCE = 0.25
PRESS_COLLAPSE_CHANCE = 0.4
VAR_VOID_CHANCE = 0.35
REASSIGN_CHANCE = 0.3
# A press that collapses starts high and falls well below the league's range.
HIGH_PRESS = 0.85
COLLAPSED_PRESS = 0.15
COLLAPSED_TEMPO = 0.35
COLLAPSE_MINUTES = range(50, 71)
STYLE_RANGE = (0.35, 0.75)


def _minutes(rng: random.Random, count: int) -> list[int]:
    """`count` scripted minutes, apart enough for each moment's own football."""
    chosen: list[int] = []
    candidates = [m for m in range(FIRST_MINUTE, LAST_MINUTE + 1) if m != HALF_TIME_MINUTE]
    rng.shuffle(candidates)
    for minute in candidates:
        if len(chosen) == count:
            break
        if all(abs(minute - other) >= MIN_MINUTES_APART for other in chosen):
            chosen.append(minute)
    return sorted(chosen)


def _style(rng: random.Random, *, pressing: float | None = None) -> TeamStyle:
    low, high = STYLE_RANGE

    def dial() -> float:
        return round(rng.uniform(low, high), 2)

    return TeamStyle(
        pressing=pressing if pressing is not None else dial(),
        directness=dial(),
        width=dial(),
        tempo=dial(),
    )


def _corrections(rng: random.Random, goals: list[ScriptedGoal]) -> list[Directive]:
    """A goal VAR rules out, and another whose scorer is reassigned, each by chance."""
    corrections: list[Directive] = []
    # VAR needs about two minutes, so a first-half goal is reviewable only well before half-time.
    reviewable = [
        g for g in goals if g.minute > HALF_TIME_MINUTE or g.minute <= LAST_FIRST_HALF_VAR_MINUTE
    ]
    voided = rng.choice(reviewable) if reviewable and rng.random() < VAR_VOID_CHANCE else None
    if voided is not None:
        corrections.append(VarVoid(club=voided.club, goal_minute=voided.minute))
    others = [g for g in goals if g is not voided]
    if others and rng.random() < REASSIGN_CHANCE:
        reassigned = rng.choice(others)
        corrections.append(ScorerReassigned(club=reassigned.club, goal_minute=reassigned.minute))
    return corrections


def _match(number: int) -> MatchSetup:
    rng = random.Random(f"benchmark:{number}")
    home, away = rng.sample(CLUB_CODES, 2)
    goal_count = rng.choices(GOAL_COUNTS, weights=GOAL_WEIGHTS)[0]
    red = rng.random() < RED_CARD_CHANCE
    minutes = _minutes(rng, goal_count + int(red))
    rng.shuffle(minutes)
    goals = [ScriptedGoal(club=rng.choice((home, away)), minute=m) for m in minutes[:goal_count]]
    directives: list[Directive] = [*goals]
    if red:
        directives.append(RedCard(club=rng.choice((home, away)), minute=minutes[goal_count]))
    presser = rng.choice((home, away)) if rng.random() < PRESS_COLLAPSE_CHANCE else None
    if presser is not None:
        directives.append(
            StyleShift(
                club=presser,
                minute=rng.choice(COLLAPSE_MINUTES),
                label=f"{presser} press collapses",
                pressing=COLLAPSED_PRESS,
                tempo=COLLAPSED_TEMPO,
            )
        )
    directives.extend(_corrections(rng, goals))
    formations = sorted(FORMATIONS)
    return MatchSetup(
        match_id=f"m{number}",
        seed=number * 7919,
        kickoff=KICKOFF,
        home=TeamSetup(
            squad=generate_squad(home, seed=SQUAD_SEED),
            formation=rng.choice(formations),
            style=_style(rng, pressing=HIGH_PRESS if presser == home else None),
        ),
        away=TeamSetup(
            squad=generate_squad(away, seed=SQUAD_SEED),
            formation=rng.choice(formations),
            style=_style(rng, pressing=HIGH_PRESS if presser == away else None),
        ),
        storyline=Storyline(
            name=f"Benchmark match {number - FIRST_MATCH_NUMBER + 1}",
            natural_goals=False,
            directives=tuple(sorted(directives, key=_minute_of)),
        ),
    )


def _minute_of(directive: Directive) -> int:
    return (
        directive.goal_minute
        if isinstance(directive, VarVoid | ScorerReassigned)
        else directive.minute
    )


def benchmark_matches(count: int = BENCHMARK_SIZE) -> tuple[MatchSetup, ...]:
    """The first `count` benchmark matches, the same on every call."""
    if not 0 < count <= BENCHMARK_SIZE:
        raise ValueError(f"the benchmark has 1-{BENCHMARK_SIZE} matches, not {count}")
    return tuple(_match(FIRST_MATCH_NUMBER + i) for i in range(count))
