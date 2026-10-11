"""Shared value types for the wire contracts: identifiers, clock, pitch geometry, timestamps.

Contracts are strict at the boundary: a value must already have the type the JSON Schema states
(no "187" for an integer, no "yes" for a boolean), identifiers use ASCII digits only and are
bounded in length, and every number has an upper bound.
"""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
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
# Elapsed-minute windows per period, allowing up to 15 minutes of added time. The synthetic league
# has no extra time or penalty shoot-outs.
FIRST_HALF_MINUTES = (0, 59)
SECOND_HALF_MINUTES = (45, 104)
MAX_BALL_SPEED_KMH = 200.0
# Upper bounds that keep every integer within int32 and well beyond any real match.
MAX_SEQ = 10_000_000
MAX_VERSION = 1_000
MAX_GOALS = 99


class WireModel(BaseModel):
    """Base for every contract: immutable, strict, camelCase on the wire, unknown fields refused."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        alias_generator=to_camel,
        # Python code constructs models by field name; the wire is parsed by alias only.
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )

    def to_wire(self) -> dict[str, Any]:
        """Serialise to the canonical JSON-compatible wire form (camelCase, UTC timestamps)."""
        return self.model_dump(mode="json")


MatchId = Annotated[str, StringConstraints(pattern=r"^m[0-9]{1,12}$")]
EventId = Annotated[str, StringConstraints(pattern=r"^m[0-9]{1,12}-e[0-9]{4,9}$")]
ClubCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
PlayerId = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}-[0-9]{2}$")]
Ratio = Annotated[float, Field(ge=0.0, le=1.0)]
SpeedKmh = Annotated[float, Field(ge=0.0, le=MAX_BALL_SPEED_KMH)]
Seq = Annotated[int, Field(ge=1, le=MAX_SEQ)]
Version = Annotated[int, Field(ge=1, le=MAX_VERSION)]


def _iso_string_only(value: object) -> object:
    # Strict mode still has to accept ISO 8601 text (JSON has no datetime type), but an epoch
    # number or other coercible value is refused.
    if isinstance(value, str | datetime):
        return value
    raise ValueError("timestamps must be ISO 8601 strings")


def _wire_timestamp(value: datetime) -> str:
    # Truncates to milliseconds (the wire precision) rather than rounding.
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


UtcTimestamp = Annotated[
    AwareDatetime,
    BeforeValidator(_iso_string_only),
    Field(strict=False),
    PlainSerializer(_wire_timestamp, return_type=str, when_used="json"),
]
"""A timezone-aware instant, always written as UTC with millisecond precision (`...Z`)."""


def club_of(player_id: str) -> str:
    """Club code a player belongs to: player IDs are `<CLUB>-<shirt>`."""
    return player_id.split("-", 1)[0]


def match_of(event_id: str) -> str:
    """Match an event belongs to: event IDs are `<match>-e<number>`."""
    return event_id.split("-e", 1)[0]


class MatchClock(WireModel):
    """Elapsed match time within a period, as shown on a broadcast clock (`67:12`)."""

    period: Literal[1, 2]
    minute: Annotated[int, Field(ge=0, le=SECOND_HALF_MINUTES[1])]
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
    home: Annotated[int, Field(ge=0, le=MAX_GOALS)]
    away: Annotated[int, Field(ge=0, le=MAX_GOALS)]
