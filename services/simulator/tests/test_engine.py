"""The match engine: deterministic, contract-valid, internally consistent, football-realistic."""

import itertools
from collections import Counter
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
from fourth_official_simulator.engine import simulate
from fourth_official_simulator.style import TeamStyle
from matches import BALANCED, PRESSING, setup


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


def _season_stats(
    seeds: range, home: TeamStyle = PRESSING, away: TeamStyle = BALANCED
) -> dict[str, float]:
    totals: Counter[str] = Counter()
    for seed in seeds:
        for event in simulate(setup(seed, home_style=home, away_style=away)):
            totals[event.type] += 1
            if isinstance(event, PassEvent):
                totals["completed"] += event.outcome == "complete"
            elif isinstance(event, ShotEvent):
                totals["on_target"] += event.outcome in {"goal", "saved"}
            elif isinstance(event, CardEvent) and event.card != "yellow":
                totals["sent_off"] += 1
            elif isinstance(event, GoalEvent):
                totals["assisted"] += event.assist_id is not None
    n = len(seeds)
    return {
        "passes": totals["PASS"] / n,
        "completion": totals["completed"] / totals["PASS"],
        "shots": totals["SHOT"] / n,
        "on_target": totals["on_target"] / totals["SHOT"],
        "goals": totals["GOAL"] / n,
        "assisted": totals["assisted"] / max(totals["GOAL"], 1),
        "fouls": totals["FOUL"] / n,
        "cards": totals["CARD"] / n,
        "sent_off": totals["sent_off"] / n,
        "offsides": totals["OFFSIDE"] / n,
    }


def test_match_statistics_match_public_norms_tightly() -> None:
    # Calibrated on 200 seeds (docs/simulator.md); bounds allow for sampling noise over 60.
    stats = _season_stats(range(4200, 4260))

    assert 880 <= stats["passes"] <= 1060
    assert 0.76 <= stats["completion"] <= 0.83
    assert 20 <= stats["shots"] <= 28
    assert 0.32 <= stats["on_target"] <= 0.44
    assert 2.2 <= stats["goals"] <= 3.3
    assert 0.65 <= stats["assisted"] <= 0.9
    assert 18 <= stats["fouls"] <= 27
    assert 2.8 <= stats["cards"] <= 5.0
    assert stats["sent_off"] <= 0.3
    assert 2.5 <= stats["offsides"] <= 7.0


EXTREME = TeamStyle(pressing=1.0, directness=1.0, width=1.0, tempo=1.0)
PASSIVE = TeamStyle(pressing=0.0, directness=0.0, width=0.0, tempo=0.0)


@pytest.mark.parametrize(
    ("home", "away"), [(EXTREME, EXTREME), (PASSIVE, PASSIVE), (EXTREME, PASSIVE)]
)
def test_style_extremes_stay_football_shaped(home: TeamStyle, away: TeamStyle) -> None:
    stats = _season_stats(range(4400, 4420), home, away)

    assert 650 <= stats["passes"] <= 1350
    assert 0.6 <= stats["completion"] <= 0.92
    assert 1.2 <= stats["goals"] <= 4.8
    assert 12 <= stats["shots"] <= 40
