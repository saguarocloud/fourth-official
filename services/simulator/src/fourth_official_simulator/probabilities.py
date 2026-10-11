"""Probabilities behind the simulated football: what a player chooses and how likely it works.

The coefficients are hand-calibrated to public aggregate norms (an open-play shot from around the
penalty spot converts at roughly a quarter of the time, a 30-metre shot rarely; short passes almost
always arrive and roughly four in five passes overall do). They model plausibility for synthetic
data, not any real league.
"""

import math
import random
from enum import StrEnum
from typing import Literal

from fourth_official_simulator.pitch import Zone
from fourth_official_simulator.style import TeamStyle

PassKind = Literal["ground", "lofted", "through", "cross", "switch"]

# Logistic expected-goals model: logit = intercept + coefficients · features.
XG_INTERCEPT = -1.1
XG_PER_METRE = -0.11  # each metre further out lowers the odds
XG_PER_RADIAN = 2.1  # a wider view of goal raises them
XG_HEADER = -0.9  # headers are harder to place
XG_PRESSURE = -1.2  # a defender in the way

# Logistic pass-completion model per pass kind.
PASS_BASE: dict[PassKind, float] = {
    "ground": 3.8,
    "switch": 2.6,
    "lofted": 2.8,
    "through": 2.2,
    "cross": 2.0,
}
PASS_PER_METRE = -0.045
PASS_PRESSURE = -2.0


def _logistic(logit: float) -> float:
    return 1.0 / (1.0 + math.exp(-logit))


def expected_goals(distance_m: float, angle_rad: float, *, header: bool, pressure: float) -> float:
    """Probability that a shot becomes a goal."""
    logit = (
        XG_INTERCEPT
        + XG_PER_METRE * distance_m
        + XG_PER_RADIAN * angle_rad
        + (XG_HEADER if header else 0.0)
        + XG_PRESSURE * pressure
    )
    return _logistic(logit)


def pass_completion(distance_m: float, pressure: float, *, kind: PassKind) -> float:
    """Probability that a pass reaches a teammate."""
    return _logistic(PASS_BASE[kind] + PASS_PER_METRE * distance_m + PASS_PRESSURE * pressure)


class Action(StrEnum):
    SHORT_PASS = "short_pass"
    LONG_PASS = "long_pass"
    THROUGH_BALL = "through_ball"
    CROSS = "cross"
    CARRY = "carry"
    SHOOT = "shoot"


def _weights(zone: Zone, style: TeamStyle, pressure: float) -> dict[Action, float]:
    d, w = style.directness, style.width
    carry = 2.0 * (1.0 - 0.5 * pressure)
    if zone is Zone.DEFENSIVE_THIRD:
        return {
            Action.SHORT_PASS: 1.0 + 6.0 * (1.0 - d),
            Action.LONG_PASS: 1.0 + 4.0 * d + 1.5 * pressure,
            Action.THROUGH_BALL: 0.3,
            Action.CARRY: carry,
        }
    if zone is Zone.MIDDLE_THIRD:
        return {
            Action.SHORT_PASS: 1.0 + 5.0 * (1.0 - d),
            Action.LONG_PASS: 1.0 + 3.0 * d,
            Action.THROUGH_BALL: 0.8 + d,
            Action.CROSS: 0.3 * w,
            Action.CARRY: carry,
            Action.SHOOT: 0.04,
        }
    if zone is Zone.FINAL_THIRD:
        return {
            Action.SHORT_PASS: 4.0,
            Action.LONG_PASS: 0.5 + d,
            Action.THROUGH_BALL: 1.2,
            Action.CROSS: 0.5 + 2.5 * w,
            Action.CARRY: carry,
            Action.SHOOT: 0.06,
        }
    return {
        Action.SHORT_PASS: 2.0,
        Action.THROUGH_BALL: 0.5,
        Action.CROSS: 0.8 * w,
        Action.CARRY: 0.5 * carry,
        Action.SHOOT: 0.3 - 0.1 * pressure,
    }


def choose_action(zone: Zone, style: TeamStyle, pressure: float, rng: random.Random) -> Action:
    """What the player on the ball does next, given where they are, how their team plays, and the
    pressure they are under."""
    weights = _weights(zone, style, pressure)
    return rng.choices(list(weights), weights=list(weights.values()))[0]
