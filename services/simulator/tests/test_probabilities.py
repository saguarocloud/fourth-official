"""Action probabilities: bounded, and monotonic where football says they should be."""

import random

from hypothesis import given
from hypothesis import strategies as st

from fourth_official_simulator.pitch import Zone
from fourth_official_simulator.probabilities import (
    Action,
    choose_action,
    expected_goals,
    pass_completion,
)
from fourth_official_simulator.style import TeamStyle

unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
distance = st.floats(min_value=1.0, max_value=60.0, allow_nan=False)
angle = st.floats(min_value=0.01, max_value=1.5, allow_nan=False)
BALANCED = TeamStyle(pressing=0.5, directness=0.5, width=0.5, tempo=0.5)


@given(distance, angle, unit)
def test_expected_goals_is_a_probability(d: float, a: float, pressure: float) -> None:
    assert 0.0 < expected_goals(d, a, header=False, pressure=pressure) < 1.0


@given(distance, angle, unit)
def test_shots_from_further_out_are_less_likely_to_score(
    d: float, a: float, pressure: float
) -> None:
    assert expected_goals(d + 5, a, header=False, pressure=pressure) < expected_goals(
        d, a, header=False, pressure=pressure
    )


@given(distance, angle, unit)
def test_a_wider_view_of_goal_helps(d: float, a: float, pressure: float) -> None:
    assert expected_goals(d, a + 0.05, header=False, pressure=pressure) > expected_goals(
        d, a, header=False, pressure=pressure
    )


@given(distance, angle)
def test_pressure_and_headers_make_scoring_harder(d: float, a: float) -> None:
    free = expected_goals(d, a, header=False, pressure=0.0)

    assert expected_goals(d, a, header=False, pressure=0.9) < free
    assert expected_goals(d, a, header=True, pressure=0.0) < free


def test_a_penalty_spot_shot_is_roughly_a_one_in_three_chance_from_open_play() -> None:
    # Open-play shots from around the spot convert at roughly 25-40% in public aggregates.
    assert 0.2 < expected_goals(11.0, 0.64, header=False, pressure=0.3) < 0.45


def test_a_long_range_shot_rarely_scores() -> None:
    assert expected_goals(30.0, 0.24, header=False, pressure=0.3) < 0.06


@given(st.floats(min_value=2.0, max_value=60.0), unit)
def test_longer_and_pressured_passes_fail_more(d: float, pressure: float) -> None:
    assert pass_completion(d + 10, pressure, kind="ground") < pass_completion(
        d, pressure, kind="ground"
    )
    assert pass_completion(d, min(pressure + 0.1, 1.0), kind="ground") <= pass_completion(
        d, pressure, kind="ground"
    )


def test_short_unpressured_passes_almost_always_arrive() -> None:
    assert pass_completion(8.0, 0.0, kind="ground") > 0.9


def test_through_balls_and_crosses_are_riskier_than_ground_passes() -> None:
    ground = pass_completion(20.0, 0.3, kind="ground")

    assert pass_completion(20.0, 0.3, kind="through") < ground
    assert pass_completion(20.0, 0.3, kind="cross") < ground


def test_nobody_shoots_from_their_own_third() -> None:
    rng = random.Random(1)

    actions = {choose_action(Zone.DEFENSIVE_THIRD, BALANCED, 0.5, rng) for _ in range(2000)}

    assert Action.SHOOT not in actions


def test_shooting_is_most_common_in_the_box() -> None:
    rng = random.Random(2)

    def shot_share(zone: Zone) -> float:
        draws = [choose_action(zone, BALANCED, 0.3, rng) for _ in range(4000)]
        return draws.count(Action.SHOOT) / len(draws)

    assert shot_share(Zone.BOX) > shot_share(Zone.FINAL_THIRD) > 0


def test_direct_teams_play_more_long_balls() -> None:
    rng_a, rng_b = random.Random(3), random.Random(3)
    direct = TeamStyle(pressing=0.5, directness=0.9, width=0.5, tempo=0.5)
    patient = TeamStyle(pressing=0.5, directness=0.1, width=0.5, tempo=0.5)

    def long_share(style: TeamStyle, rng: random.Random) -> float:
        draws = [choose_action(Zone.MIDDLE_THIRD, style, 0.3, rng) for _ in range(4000)]
        return draws.count(Action.LONG_PASS) / len(draws)

    assert long_share(direct, rng_a) > long_share(patient, rng_b)


def test_choices_are_deterministic_for_a_seeded_generator() -> None:
    first = [choose_action(Zone.FINAL_THIRD, BALANCED, 0.4, random.Random(9)) for _ in range(5)]
    second = [choose_action(Zone.FINAL_THIRD, BALANCED, 0.4, random.Random(9)) for _ in range(5)]

    assert first == second
