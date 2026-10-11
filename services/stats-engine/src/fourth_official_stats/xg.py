"""The stats engine's expected-goals model.

Independent of the simulator's own model: the pipeline measures shots, it does not peek at how
they were generated. Logistic regression on distance and angle to the goal being attacked, with
penalties for headers and pressure. Coefficients are documented in docs/metrics.md.
"""

import itertools
import math
from collections.abc import Iterable

from fourth_official_contracts import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    MatchEvent,
    SetPieceEvent,
    ShotEvent,
)
from fourth_official_stats.context import MatchContext

GOAL_WIDTH_M = 7.32
INTERCEPT = -1.0
PER_METRE = -0.105
PER_RADIAN = 2.0
HEADER = -0.85
PRESSURE = -1.1
# Penalties convert at roughly three in four; geometry alone would say about 0.3.
PENALTY_XG = 0.76


def _geometry(shot: ShotEvent, context: MatchContext) -> tuple[float, float]:
    progress = context.progress(shot.team_id, shot.clock.period, shot.origin.x)
    depth = max((1.0 - progress) * PITCH_LENGTH_M, 1e-6)
    offset = shot.origin.y - PITCH_WIDTH_M / 2
    distance = math.hypot(depth, offset)
    half = GOAL_WIDTH_M / 2
    angle = abs(math.atan2(offset + half, depth) - math.atan2(offset - half, depth))
    return distance, angle


def shot_xg(shot: ShotEvent, context: MatchContext) -> float:
    """Probability that a shot like this one becomes a goal."""
    distance, angle = _geometry(shot, context)
    logit = (
        INTERCEPT
        + PER_METRE * distance
        + PER_RADIAN * angle
        + (HEADER if shot.body_part == "head" else 0.0)
        + PRESSURE * shot.pressure
    )
    return 1.0 / (1.0 + math.exp(-logit))


def penalty_awards(events: Iterable[MatchEvent]) -> dict[str, str]:
    """Penalty shots and the awards that made them penalties: shot event ID -> set-piece event ID.
    A penalty is a shot taken straight after a penalty was awarded to the same team."""
    ordered = sorted(events, key=lambda e: e.seq)
    return {
        shot.event_id: award.event_id
        for award, shot in itertools.pairwise(ordered)
        if isinstance(shot, ShotEvent)
        and isinstance(award, SetPieceEvent)
        and award.kind == "penalty"
        and award.team_id == shot.team_id
    }
