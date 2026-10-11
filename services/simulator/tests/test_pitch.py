"""Pitch geometry: attacking frames, ends switching at half time, distances and shooting angles."""

import math

import pytest

from fourth_official_simulator.pitch import (
    GOAL_WIDTH_M,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Zone,
    attacking_to_pitch,
    distance_to_goal,
    pitch_to_attacking,
    shooting_angle,
    zone_of,
)


def test_the_home_side_attacks_towards_x_105_in_the_first_half() -> None:
    assert attacking_to_pitch(1.0, 0.5, home=True, period=1) == (PITCH_LENGTH_M, PITCH_WIDTH_M / 2)


def test_teams_switch_ends_at_half_time() -> None:
    assert attacking_to_pitch(1.0, 0.5, home=True, period=2) == (0.0, PITCH_WIDTH_M / 2)
    assert attacking_to_pitch(1.0, 0.5, home=False, period=1) == (0.0, PITCH_WIDTH_M / 2)


def test_coordinates_are_clamped_to_the_pitch() -> None:
    x, y = attacking_to_pitch(1.2, -0.3, home=True, period=1)

    assert (x, y) == (PITCH_LENGTH_M, 0.0)


@pytest.mark.parametrize(
    ("progress", "zone"),
    [
        (0.1, Zone.DEFENSIVE_THIRD),
        (0.5, Zone.MIDDLE_THIRD),
        (0.8, Zone.FINAL_THIRD),
        (0.95, Zone.BOX),
    ],
)
def test_zones_follow_progress_up_the_pitch(progress: float, zone: Zone) -> None:
    assert zone_of(progress, 0.5) is zone


def test_wide_positions_near_goal_are_final_third_not_box() -> None:
    assert zone_of(0.95, 0.05) is Zone.FINAL_THIRD


def test_distance_to_goal_is_measured_to_the_centre_of_the_goal_line() -> None:
    assert distance_to_goal(1.0, 0.5) == pytest.approx(0.0)
    assert distance_to_goal(0.0, 0.5) == pytest.approx(PITCH_LENGTH_M)


def test_the_shooting_angle_narrows_with_distance_and_width() -> None:
    central_close = shooting_angle(0.9, 0.5)
    central_far = shooting_angle(0.7, 0.5)
    wide_close = shooting_angle(0.9, 0.1)

    assert central_close > central_far > 0
    assert central_close > wide_close > 0


def test_the_angle_from_the_penalty_spot_matches_the_goal_geometry() -> None:
    spot = 1 - 11 / PITCH_LENGTH_M
    expected = 2 * math.atan((GOAL_WIDTH_M / 2) / 11)

    assert shooting_angle(spot, 0.5) == pytest.approx(expected)


def test_pitch_to_attacking_inverts_attacking_to_pitch() -> None:
    for home in (True, False):
        for period in (1, 2):
            x, y = attacking_to_pitch(0.8, 0.3, home=home, period=period)
            assert pitch_to_attacking(x, y, home=home, period=period) == pytest.approx((0.8, 0.3))
