"""The Proving Ground's benchmark: many seeded matches, each with a storyline planted in it."""

from collections import Counter
from functools import cache

from fourth_official_contracts import GroundTruth
from fourth_official_simulator.benchmark import BENCHMARK_SIZE, benchmark_matches
from fourth_official_simulator.engine import MatchSetup, play
from fourth_official_simulator.squads import CLUB_CODES


@cache
def played(count: int = 40) -> tuple[tuple[MatchSetup, GroundTruth], ...]:
    return tuple((setup, play(setup).ground_truth) for setup in benchmark_matches(count))


def test_the_full_benchmark_is_a_hundred_matches() -> None:
    assert BENCHMARK_SIZE == 100
    assert len(benchmark_matches()) == BENCHMARK_SIZE


def test_the_benchmark_is_the_same_every_time() -> None:
    assert benchmark_matches(10) == benchmark_matches(10)


def test_a_smaller_benchmark_is_the_start_of_the_full_one() -> None:
    assert benchmark_matches(20) == benchmark_matches()[:20]


def test_matches_are_named_apart_from_the_demo_matchday() -> None:
    ids = [s.match_id for s in benchmark_matches()]

    assert ids[:3] == ["m1001", "m1002", "m1003"]
    assert len(set(ids)) == len(ids)
    assert len({s.seed for s in benchmark_matches()}) == BENCHMARK_SIZE


def test_every_match_is_two_different_league_clubs() -> None:
    for setup in benchmark_matches():
        home, away = setup.home.squad.club, setup.away.squad.club
        assert home != away
        assert {home, away} <= set(CLUB_CODES)


def test_every_match_plays_and_records_what_was_planted() -> None:
    for setup, truth in played():
        assert truth.match_id == setup.match_id
        assert len(truth.storylines) >= len(setup.storyline.directives) - len(
            setup.storyline.shifts
        )


def test_the_benchmark_plants_every_kind_of_storyline_the_pipeline_must_handle() -> None:
    kinds = Counter(s.kind for _, truth in played() for s in truth.storylines)

    for kind in ("goal", "red_card", "var_overturn", "scorer_reassigned", "pressing_collapse"):
        assert kinds[kind] >= 3, kinds


def test_some_matches_are_quiet() -> None:
    goals = [sum(1 for s in truth.storylines if s.kind == "goal") for _, truth in played()]

    assert 0 in goals
    assert max(goals) >= 3
