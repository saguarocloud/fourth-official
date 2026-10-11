"""Team style: four dials that shape how a team plays, and so what its data looks like.

Storylines change these dials over time (a press that fades with fatigue, a switch to a deeper
block), which is what makes tactical shifts real and detectable downstream.
"""

from dataclasses import dataclass, fields, replace


@dataclass(frozen=True, slots=True)
class TeamStyle:
    # How hard and how high the team presses without the ball.
    pressing: float
    # Preference for forward, longer passes over keeping the ball.
    directness: float
    # How much the team uses the flanks.
    width: float
    # How quickly the team moves the ball.
    tempo: float

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field.name} must be between 0 and 1, got {value}")

    def with_changes(self, **changes: float) -> "TeamStyle":
        """A new style with some dials changed; the original is untouched."""
        return replace(self, **changes)
