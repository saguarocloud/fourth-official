"""Every metric against a hand-computed fixture: its value and its evidence (input event IDs)."""

import math

import pytest

from events import interception, pass_, penalty_awarded, pressure, shot, tackle, turnover
from fourth_official_contracts import MatchEvent
from fourth_official_stats.context import MatchContext
from fourth_official_stats.metrics import (
    control_chaos,
    field_tilt,
    momentum,
    pass_completion,
    pass_difficulty,
    passes,
    possession,
    ppda,
    pressing_intensity,
    pressure_on_passer,
    shots,
    shots_on_target,
    xg,
)
from fourth_official_stats.xg import shot_xg

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")


def ids(*seqs: int) -> tuple[str, ...]:
    return tuple(f"m42-e{s:04d}" for s in seqs)


# --- Passing and possession ------------------------------------------------------------------
PASSING = (
    pass_(1, 10, "HCY"),
    pass_(2, 10, "HCY", complete=False),
    pass_(3, 11, "HCY"),
    pass_(4, 11, "NGT"),
)


def test_passes_count_only_the_teams_own_passes() -> None:
    result = passes(PASSING, CTX, "HCY")

    assert result.value == 3
    assert result.inputs == ids(1, 2, 3)


def test_pass_completion_is_completed_over_attempted() -> None:
    result = pass_completion(PASSING, CTX, "HCY")

    assert result.value == pytest.approx(2 / 3)
    assert result.inputs == ids(1, 2, 3)


def test_pass_completion_is_undefined_without_passes() -> None:
    assert pass_completion(PASSING, CTX, "SLT").value is None


def test_possession_is_the_teams_share_of_all_passes() -> None:
    result = possession(PASSING, CTX, "HCY")

    assert result.value == pytest.approx(0.75)
    assert result.inputs == ids(1, 2, 3, 4)


def test_field_tilt_is_the_share_of_final_third_passes() -> None:
    # First half: HCY attacks towards x = 105, so its final third starts at x = 70;
    # NGT attacks towards x = 0, so its final third ends at x = 35.
    events = (
        pass_(1, 20, "HCY", origin=(80.0, 30.0)),
        pass_(2, 20, "HCY", origin=(75.0, 30.0)),
        pass_(3, 21, "HCY", origin=(40.0, 30.0)),  # not in the final third
        pass_(4, 21, "NGT", origin=(20.0, 30.0)),
    )

    result = field_tilt(events, CTX, "HCY")

    assert result.value == pytest.approx(2 / 3)
    assert result.inputs == ids(1, 2, 4)


def test_field_tilt_follows_the_switch_of_ends_at_half_time() -> None:
    events = (pass_(1, 60, "HCY", origin=(20.0, 30.0)), pass_(2, 60, "NGT", origin=(80.0, 30.0)))

    assert field_tilt(events, CTX, "HCY").value == pytest.approx(0.5)


# --- Shooting --------------------------------------------------------------------------------
SHOOTING = (
    shot(1, 30, "HCY", at=(94.0, 34.0), outcome="goal"),
    shot(2, 31, "HCY", at=(80.0, 20.0), outcome="off_target"),
    shot(3, 32, "NGT", at=(12.0, 34.0), outcome="saved"),
)


def test_shots_and_shots_on_target() -> None:
    assert shots(SHOOTING, CTX, "HCY").value == 2
    assert shots_on_target(SHOOTING, CTX, "HCY").value == 1
    assert shots_on_target(SHOOTING, CTX, "HCY").inputs == ids(1, 2)


def test_xg_sums_the_model_over_the_teams_shots() -> None:
    # Shot 1: penalty spot (0.2952). Shot 2: 25 m out and 14 m wide of centre.
    second = shot_xg(SHOOTING[1], CTX)

    assert second < 0.05
    assert xg(SHOOTING, CTX, "HCY").value == pytest.approx(0.2952 + second, abs=1e-4)


def test_the_xg_model_reads_the_goal_the_shooter_attacks() -> None:
    # 11 m out, central: HCY attacks x = 105 in the first half, NGT attacks x = 0.
    home_spot = shot(1, 10, "HCY", at=(94.0, 34.0))
    away_spot = shot(2, 10, "NGT", at=(11.0, 34.0))

    assert shot_xg(home_spot, CTX) == pytest.approx(shot_xg(away_spot, CTX))
    assert 0.15 < shot_xg(home_spot, CTX) < 0.45


def test_xg_falls_with_distance_pressure_and_headers() -> None:
    close = shot_xg(shot(1, 10, "HCY", at=(97.0, 34.0)), CTX)
    far = shot_xg(shot(2, 10, "HCY", at=(80.0, 34.0)), CTX)
    pressed = shot_xg(shot(3, 10, "HCY", at=(97.0, 34.0), pressure=0.9), CTX)
    header = shot_xg(shot(4, 10, "HCY", at=(97.0, 34.0), body_part="head"), CTX)

    assert close > far
    assert close > pressed
    assert close > header


def test_momentum_cites_every_shot_in_the_window() -> None:
    assert momentum(SHOOTING, CTX, "HCY").inputs == ids(1, 2, 3)


# --- Pressing --------------------------------------------------------------------------------
def test_ppda_is_opponent_passes_per_defensive_action_in_their_build_up_zone() -> None:
    # HCY presses NGT. In the first half NGT defends the goal at x = 105, so NGT's own 60% of the
    # pitch is x >= 42.
    events: tuple[MatchEvent, ...] = (
        *(pass_(i, 10, "NGT", origin=(70.0, 30.0)) for i in range(1, 7)),
        pass_(7, 10, "NGT", origin=(30.0, 30.0)),  # outside the zone
        tackle(8, 11, "HCY", "NGT", at=(60.0, 30.0)),
        interception(9, 11, "HCY", at=(80.0, 30.0)),
        tackle(10, 11, "HCY", "NGT", at=(20.0, 30.0)),  # outside the zone
    )

    result = ppda(events, CTX, "HCY")

    assert result.value == pytest.approx(3.0)
    assert result.inputs == ids(1, 2, 3, 4, 5, 6, 8, 9)


def test_ppda_is_undefined_without_defensive_actions() -> None:
    assert ppda((pass_(1, 10, "NGT", origin=(70.0, 30.0)),), CTX, "HCY").value is None


def test_pressing_intensity_is_pressure_events_per_minute_of_the_window() -> None:
    events = tuple(pressure(i, 10, "HCY", "NGT") for i in range(1, 11))

    result = pressing_intensity(events, CTX, "HCY", minutes=5.0)

    assert result.value == pytest.approx(2.0)
    assert result.inputs == ids(*range(1, 11))


# --- Pass difficulty -------------------------------------------------------------------------
def test_pass_difficulty_rates_distance_pressure_and_kind() -> None:
    easy = pass_(2, 10, "HCY", origin=(40.0, 34.0), end=(45.0, 34.0))
    hard = pass_(4, 10, "HCY", origin=(40.0, 34.0), end=(80.0, 34.0), kind="through")
    pressed_on = pressure(3, 10, "NGT", "HCY", intensity=1.0)

    easy_rating = pass_difficulty(easy, pressure=0.0)
    hard_rating = pass_difficulty(hard, pressure=pressed_on.intensity)

    # easy: 0.45 * 5/50 + 0 + 0.2 * 0.2 = 0.085 -> 8.5
    assert easy_rating == pytest.approx(8.5)
    # hard: 0.45 * 40/50 + 0.35 * 1.0 + 0.2 * 0.8 = 0.87 -> 87.0
    assert hard_rating == pytest.approx(87.0)


# --- Control versus chaos --------------------------------------------------------------------
def test_control_chaos_index_matches_its_documented_formula() -> None:
    # 5 minutes, 2 turnovers (0.4 per minute), 4 passes in 3 chains, all at one spot (zero entropy).
    events = (
        pass_(1, 10, "HCY"),
        pass_(2, 10, "HCY"),
        turnover(3, 11, "NGT"),
        pass_(4, 11, "NGT"),
        turnover(5, 12, "HCY"),
        pass_(6, 12, "HCY"),
    )

    result = control_chaos(events, CTX, minutes=5.0)

    turnover_term = min(0.4 / 4.0, 1.0)  # 0.1
    chain_term = 1.0 - min((4 / 3) / 8.0, 1.0)  # 0.8333
    entropy_term = 0.0
    expected = 100 * (0.4 * turnover_term + 0.4 * chain_term + 0.2 * entropy_term)
    assert result.value == pytest.approx(expected)
    assert result.inputs == ids(1, 2, 3, 4, 5, 6)
    assert math.isfinite(result.value or 0.0)


def test_metrics_refuse_a_club_that_is_not_playing() -> None:
    with pytest.raises(ValueError, match="does not play"):
        momentum(SHOOTING, CTX, "SLT")


def test_control_chaos_is_undefined_for_a_zero_length_window() -> None:
    assert control_chaos(PASSING, CTX, minutes=0.0).value is None


# --- Hand-computed constants -------------------------------------------------------------------
# logit = -1.0 - 0.105 d + 2.0 a (- 0.85 header - 1.1 pressure); a = goal-mouth angle.
def _xg_by_hand(distance: float, angle: float) -> float:
    return 1 / (1 + math.exp(-(-1.0 - 0.105 * distance + 2.0 * angle)))


def test_xg_from_the_penalty_spot_matches_the_documented_coefficients() -> None:
    angle = 2 * math.atan(3.66 / 11)  # 0.6424 rad

    assert shot_xg(shot(1, 10, "HCY", at=(94.0, 34.0)), CTX) == pytest.approx(0.2952, abs=1e-4)
    assert shot_xg(shot(1, 10, "HCY", at=(94.0, 34.0)), CTX) == pytest.approx(
        _xg_by_hand(11, angle)
    )


def test_xg_reads_the_goal_attacked_after_half_time() -> None:
    # Second half: HCY attacks x = 0, so x = 11 is the penalty spot.
    assert shot_xg(shot(1, 60, "HCY", at=(11.0, 34.0)), CTX) == pytest.approx(0.2952, abs=1e-4)


def test_a_shot_at_the_wrong_end_is_almost_worthless() -> None:
    # NGT attacks x = 0 in the first half; from x = 94 it is 94 m from goal.
    assert shot_xg(shot(1, 10, "NGT", at=(94.0, 34.0)), CTX) < 1e-4


def test_penalties_use_the_penalty_conversion_rate_not_open_play_geometry() -> None:
    events = (penalty_awarded(1, 20, "HCY"), shot(2, 20, "HCY", at=(94.0, 34.0), outcome="goal"))

    assert xg(events, CTX, "HCY").value == pytest.approx(0.76)


def test_momentum_is_positive_for_the_side_creating_more() -> None:
    events = (shot(1, 30, "HCY", at=(94.0, 34.0)), shot(2, 31, "NGT", at=(30.0, 34.0)))

    value = momentum(events, CTX, "HCY").value

    assert value is not None
    assert value == pytest.approx(0.2952 - shot_xg(events[1], CTX), abs=1e-4)
    assert value > 0


def test_ppda_follows_the_switch_of_ends() -> None:
    # Second half: NGT defends the goal at x = 0, so its own 60% is x <= 63.
    events: tuple[MatchEvent, ...] = (
        pass_(1, 60, "NGT", origin=(30.0, 30.0)),
        pass_(2, 60, "NGT", origin=(30.0, 30.0)),
        pass_(3, 60, "NGT", origin=(80.0, 30.0)),  # outside its own 60%
        tackle(4, 61, "HCY", "NGT", at=(40.0, 30.0)),
    )

    result = ppda(events, CTX, "HCY")

    assert result.value == pytest.approx(2.0)
    assert result.inputs == ids(1, 2, 4)


def test_control_chaos_counts_scattered_play_including_the_pitch_edges() -> None:
    # Four located events in four different cells of the 6 x 4 grid, including x = 105, y = 68.
    events = (
        pass_(1, 10, "HCY", origin=(0.0, 0.0)),
        pass_(2, 10, "HCY", origin=(105.0, 68.0)),
        pass_(3, 10, "HCY", origin=(52.0, 30.0)),
        pass_(4, 10, "HCY", origin=(20.0, 60.0)),
    )

    result = control_chaos(events, CTX, minutes=5.0)

    entropy = math.log(4) / math.log(24)
    chain = 1.0 - min(4 / 8.0, 1.0)
    assert result.value == pytest.approx(100 * (0.4 * 0.0 + 0.4 * chain + 0.2 * entropy))


def test_control_chaos_is_undefined_when_nothing_happened() -> None:
    assert control_chaos((), CTX, minutes=5.0).value is None


@pytest.mark.parametrize(
    ("kind", "factor"),
    [("ground", 0.2), ("lofted", 0.5), ("switch", 0.6), ("cross", 0.7), ("through", 0.8)],
)
def test_pass_difficulty_kind_factors(kind: str, factor: float) -> None:
    made = pass_(1, 10, "HCY", origin=(40.0, 34.0), end=(60.0, 34.0), kind=kind)

    assert pass_difficulty(made, pressure=0.0) == pytest.approx(
        round(100 * (0.45 * 20 / 50 + 0.2 * factor), 1)
    )


def test_empty_sums_are_floats() -> None:
    assert isinstance(xg((), CTX, "HCY").value, float)


def test_pressure_on_the_passer_is_read_from_the_press_just_before_the_pass() -> None:
    pressed = pressure(1, 10, "NGT", "HCY", intensity=0.8)
    made = pass_(2, 10, "HCY")
    by_seq: dict[int, MatchEvent] = {1: pressed, 2: made}

    assert pressure_on_passer(made, by_seq) == 0.8
    assert pressure_on_passer(made, {2: made}) == 0.0


def test_a_press_on_someone_else_does_not_count() -> None:
    elsewhere = pressure(1, 10, "NGT", "BRM", intensity=0.8)
    made = pass_(2, 10, "HCY")

    assert pressure_on_passer(made, {1: elsewhere, 2: made}) == 0.0


def test_control_chaos_with_turnovers_but_no_located_play() -> None:
    # Two turnovers in 5 minutes, no passes: T = 0.1, C = 1 (no chains), E = 0 (nothing located).
    events = (turnover(1, 10, "NGT"), turnover(2, 11, "HCY"))

    assert control_chaos(events, CTX, minutes=5.0).value == pytest.approx(
        100 * (0.4 * 0.1 + 0.4 * 1.0)
    )
