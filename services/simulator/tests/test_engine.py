"""The match engine: deterministic, contract-valid, internally consistent, football-realistic."""

import itertools
from collections import Counter
from datetime import UTC, datetime
from functools import cache

import pytest

from fourth_official_contracts import (
    MATCH_EVENT_TYPES,
    CardEvent,
    GoalEvent,
    MatchEvent,
    PassEvent,
    PeriodEndEvent,
    PeriodStartEvent,
    ShotEvent,
    SubstitutionEvent,
    parse_match_event,
)
from fourth_official_simulator.engine import MatchSetup, TeamSetup, simulate
from fourth_official_simulator.squads import generate_squad
from fourth_official_simulator.style import TeamStyle

KICKOFF = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)
PRESSING = TeamStyle(pressing=0.75, directness=0.4, width=0.6, tempo=0.65)
BALANCED = TeamStyle(pressing=0.5, directness=0.5, width=0.5, tempo=0.5)


def setup(seed: int = 4207, match_id: str = "m42") -> MatchSetup:
    return MatchSetup(
        match_id=match_id,
        seed=seed,
        kickoff=KICKOFF,
        home=TeamSetup(squad=generate_squad("HCY", seed=1), formation="4-3-3", style=PRESSING),
        away=TeamSetup(squad=generate_squad("NGT", seed=1), formation="4-2-3-1", style=BALANCED),
    )


@cache
def match(seed: int = 4207) -> tuple[MatchEvent, ...]:
    return simulate(setup(seed))


def test_the_same_setup_always_produces_the_same_match() -> None:
    assert simulate(setup()) == simulate(setup())


def test_different_seeds_produce_different_matches() -> None:
    assert match(4207) != match(4208)


def test_every_event_is_a_valid_contract_model_that_survives_the_wire() -> None:
    for event in match():
        assert isinstance(event, MATCH_EVENT_TYPES)
        assert parse_match_event(event.to_wire()) == event


def test_events_are_numbered_and_timed_in_order() -> None:
    events = match()

    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert all(e.event_id == f"m42-e{e.seq:04d}" for e in events)
    assert all(a.wall_clock <= b.wall_clock for a, b in itertools.pairwise(events))


def test_the_match_has_two_halves_that_start_and_end() -> None:
    events = match()
    markers = [
        (type(e), e.clock.period)
        for e in events
        if isinstance(e, PeriodStartEvent | PeriodEndEvent)
    ]

    assert markers == [
        (PeriodStartEvent, 1),
        (PeriodEndEvent, 1),
        (PeriodStartEvent, 2),
        (PeriodEndEvent, 2),
    ]
    assert isinstance(events[0], PeriodStartEvent)
    assert isinstance(events[-1], PeriodEndEvent)


def test_the_score_after_each_goal_counts_every_goal_so_far() -> None:
    home = away = 0
    for goal in (e for e in match() if isinstance(e, GoalEvent)):
        if goal.team_id == "HCY":
            home += 1
        else:
            away += 1
        assert (goal.score_after.home, goal.score_after.away) == (home, away)


def test_each_goal_follows_its_shot() -> None:
    by_id = {e.event_id: e for e in match()}
    for goal in (e for e in match() if isinstance(e, GoalEvent)):
        assert goal.shot_event_id is not None
        shot = by_id[goal.shot_event_id]
        assert isinstance(shot, ShotEvent)
        assert shot.outcome == "goal"
        assert shot.seq < goal.seq


def test_teams_attack_opposite_ends_and_switch_at_half_time() -> None:
    def mean_x(period: int, team: str) -> float:
        xs = [
            e.origin.x
            for e in match()
            if isinstance(e, ShotEvent) and e.clock.period == period and e.team_id == team
        ]
        return sum(xs) / len(xs) if xs else 52.5

    assert mean_x(1, "HCY") > 52.5 > mean_x(2, "HCY")


def test_a_sent_off_player_takes_no_further_part() -> None:
    for seed in range(4200, 4230):
        events = match(seed)
        for i, card in enumerate(events):
            if isinstance(card, CardEvent) and card.card in {"red", "second_yellow"}:
                later = events[i + 1 :]
                assert all(getattr(e, "player_id", None) != card.player_id for e in later)


def test_substitutes_only_act_after_coming_on() -> None:
    events = match()
    for i, sub in enumerate(events):
        if isinstance(sub, SubstitutionEvent):
            assert all(getattr(e, "player_id", None) != sub.player_on_id for e in events[:i])
            assert all(getattr(e, "player_id", None) != sub.player_off_id for e in events[i + 1 :])


@pytest.mark.parametrize("seed", range(4200, 4210))
def test_each_team_makes_at_most_three_substitutions(seed: int) -> None:
    subs = Counter(e.team_id for e in match(seed) if isinstance(e, SubstitutionEvent))

    assert all(count <= 3 for count in subs.values())


def test_match_statistics_fall_in_realistic_ranges_across_many_seeds() -> None:
    # Public aggregate norms for top-flight matches, generously bounded for a synthetic engine.
    seeds = range(4200, 4230)
    passes = completed = shots = on_target = goals = cards = 0
    for seed in seeds:
        for event in match(seed):
            if isinstance(event, PassEvent):
                passes += 1
                completed += event.outcome == "complete"
            elif isinstance(event, ShotEvent):
                shots += 1
                on_target += event.outcome in {"goal", "saved"}
            elif isinstance(event, GoalEvent):
                goals += 1
            elif isinstance(event, CardEvent):
                cards += 1
    n = len(seeds)

    assert 650 <= passes / n <= 1150
    assert 0.72 <= completed / passes <= 0.88
    assert 18 <= shots / n <= 32
    assert 0.25 <= on_target / shots <= 0.45
    assert 1.8 <= goals / n <= 3.8
    assert 1.5 <= cards / n <= 6.0


def test_goals_straight_after_a_completed_pass_credit_the_passer() -> None:
    assisted = 0
    for seed in range(4200, 4230):
        events = match(seed)
        by_id = {e.event_id: e for e in events}
        for goal in (e for e in events if isinstance(e, GoalEvent)):
            if goal.assist_id is None:
                continue
            assisted += 1
            shot = by_id[goal.shot_event_id or ""]
            before = [e for e in events if e.seq < shot.seq and isinstance(e, PassEvent)][-1]
            assert before.outcome == "complete"
            assert before.player_id == goal.assist_id
            assert before.receiver_id == goal.scorer_id
    assert assisted > 0
