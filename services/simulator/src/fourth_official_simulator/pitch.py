"""Pitch geometry in two frames.

The simulator reasons in an *attacking frame*: progress 0 is the team's own goal line and 1 is the
opponent's, lateral 0..1 runs across the pitch. Events are written in *pitch coordinates*: metres
from the home side's left corner flag, with teams switching ends at half time.
"""

import math
from enum import StrEnum

from fourth_official_contracts import PITCH_LENGTH_M, PITCH_WIDTH_M

__all__ = [
    "BOX_DEPTH_M",
    "BOX_WIDTH_M",
    "GOAL_WIDTH_M",
    "PITCH_LENGTH_M",
    "PITCH_WIDTH_M",
    "Zone",
    "attacking_to_pitch",
    "distance_to_goal",
    "pitch_to_attacking",
    "shooting_angle",
    "zone_of",
]

GOAL_WIDTH_M = 7.32
# The penalty area is 16.5 m deep and 40.32 m wide.
BOX_DEPTH_M = 16.5
BOX_WIDTH_M = 40.32


class Zone(StrEnum):
    DEFENSIVE_THIRD = "defensive_third"
    MIDDLE_THIRD = "middle_third"
    FINAL_THIRD = "final_third"
    BOX = "box"


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def attacking_to_pitch(
    progress: float, lateral: float, *, home: bool, period: int
) -> tuple[float, float]:
    """Convert attacking-frame coordinates to pitch metres for the team in possession."""
    progress, lateral = _clamp(progress), _clamp(lateral)
    attacks_right = home == (period == 1)
    x = progress if attacks_right else 1.0 - progress
    y = lateral if attacks_right else 1.0 - lateral
    return round(x * PITCH_LENGTH_M, 2), round(y * PITCH_WIDTH_M, 2)


def pitch_to_attacking(x: float, y: float, *, home: bool, period: int) -> tuple[float, float]:
    """Convert pitch metres back to the attacking frame of a team (the inverse of
    `attacking_to_pitch`)."""
    attacks_right = home == (period == 1)
    progress, lateral = x / PITCH_LENGTH_M, y / PITCH_WIDTH_M
    return (progress, lateral) if attacks_right else (1.0 - progress, 1.0 - lateral)


def zone_of(progress: float, lateral: float) -> Zone:
    """Which part of the pitch a point is in, from the attacking team's point of view."""
    metres_from_goal = (1.0 - progress) * PITCH_LENGTH_M
    metres_from_centre = abs(lateral - 0.5) * PITCH_WIDTH_M
    if metres_from_goal <= BOX_DEPTH_M and metres_from_centre <= BOX_WIDTH_M / 2:
        return Zone.BOX
    if progress >= 2 / 3:
        return Zone.FINAL_THIRD
    if progress >= 1 / 3:
        return Zone.MIDDLE_THIRD
    return Zone.DEFENSIVE_THIRD


def distance_to_goal(progress: float, lateral: float) -> float:
    """Metres from the point to the centre of the opponent's goal line."""
    dx = (1.0 - progress) * PITCH_LENGTH_M
    dy = (lateral - 0.5) * PITCH_WIDTH_M
    return math.hypot(dx, dy)


def shooting_angle(progress: float, lateral: float) -> float:
    """Angle in radians subtended by the goal mouth: the visible target for a shot."""
    dx = max((1.0 - progress) * PITCH_LENGTH_M, 1e-6)
    dy = (lateral - 0.5) * PITCH_WIDTH_M
    half = GOAL_WIDTH_M / 2
    return abs(math.atan2(dy + half, dx) - math.atan2(dy - half, dx))
