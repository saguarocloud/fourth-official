"""Shared value types for the wire contracts: identifiers, clock, pitch geometry, timestamps."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)
from pydantic.alias_generators import to_camel

# Pitch dimensions in metres (the synthetic league plays on 105 by 68 metre pitches).
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
# Elapsed-minute windows per period, allowing up to 15 minutes of added time.
FIRST_HALF_MINUTES = (0, 59)
SECOND_HALF_MINUTES = (45, 104)
MAX_BALL_SPEED_KMH = 200.0


class WireModel(BaseModel):
    """Base for every contract: immutable, camelCase on the wire, unknown fields refused."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        strict=False,
    )

    def to_wire(self) -> dict[str, object]:
        """Serialise to the canonical JSON-compatible wire form."""
        # Unset optional fields (for example, unchanged fields of an amendment) are omitted.
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


MatchId = Annotated[str, StringConstraints(pattern=r"^m\d+$")]
EventId = Annotated[str, StringConstraints(pattern=r"^m\d+-e\d{4,}$")]
ClubCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
PlayerId = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}-\d{2}$")]
Ratio = Annotated[float, Field(ge=0.0, le=1.0)]
SpeedKmh = Annotated[float, Field(ge=0.0, le=MAX_BALL_SPEED_KMH)]


def _wire_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


UtcTimestamp = Annotated[
    AwareDatetime,
    PlainSerializer(_wire_timestamp, return_type=str, when_used="json"),
]
"""A timezone-aware instant, always written as UTC with millisecond precision (`...Z`)."""


def club_of(player_id: str) -> str:
    """Club code a player belongs to: player IDs are `<CLUB>-<shirt>`."""
    return player_id.split("-", 1)[0]


class MatchClock(WireModel):
    """Elapsed match time within a period, as shown on a broadcast clock (`67:12`)."""

    period: Literal[1, 2]
    minute: Annotated[int, Field(ge=0)]
    second: Annotated[int, Field(ge=0, le=59)]

    @model_validator(mode="after")
    def _minute_belongs_to_period(self) -> "MatchClock":
        low, high = FIRST_HALF_MINUTES if self.period == 1 else SECOND_HALF_MINUTES
        if not low <= self.minute <= high:
            raise ValueError(f"minute {self.minute} is outside period {self.period} ({low}-{high})")
        return self


class PitchPoint(WireModel):
    """A location in metres from the home side's left corner flag."""

    x: Annotated[float, Field(ge=0.0, le=PITCH_LENGTH_M)]
    y: Annotated[float, Field(ge=0.0, le=PITCH_WIDTH_M)]


class Score(WireModel):
    home: Annotated[int, Field(ge=0)]
    away: Annotated[int, Field(ge=0)]
