"""Corrections: the source of truth changed after events were published.

A VAR decision can void a goal; the accreditation panel can reassign its scorer. The pipeline
must find and fix everything it already published from the original event.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.primitives import (
    EventId,
    MatchClock,
    MatchId,
    PlayerId,
    UtcTimestamp,
    WireModel,
)

CorrectionId = Annotated[str, StringConstraints(pattern=r"^c-\d{4,}$")]
CorrectionReason = Literal[
    "VAR_OFFSIDE",
    "VAR_FOUL",
    "VAR_HANDBALL",
    "ACCREDITATION_PANEL",
    "PROVIDER_RESTATEMENT",
]


class CorrectionEnvelope(WireModel):
    correction_id: CorrectionId
    match_id: MatchId
    target_event_id: EventId
    reason: CorrectionReason
    issued_at: UtcTimestamp
    # The corrected event's new version; always above the original's 1.
    new_version: Annotated[int, Field(ge=2)]

    @model_validator(mode="after")
    def _target_belongs_to_match(self) -> "CorrectionEnvelope":
        if not self.target_event_id.startswith(f"{self.match_id}-e"):
            raise ValueError(
                f"event {self.target_event_id} does not belong to match {self.match_id}"
            )
        return self


class EventVoided(CorrectionEnvelope):
    """The event no longer stands (for example, a goal disallowed by VAR)."""

    kind: Literal["EVENT_VOIDED"]


class Amendment(WireModel):
    """Fields of the target event that change. At least one must be set."""

    scorer_id: PlayerId | None = None
    assist_id: PlayerId | None = None
    own_goal: bool | None = None
    card: Literal["yellow", "second_yellow", "red"] | None = None
    clock: MatchClock | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> "Amendment":
        if not self.model_fields_set:
            raise ValueError("an amendment must change at least one field")
        return self


class EventAmended(CorrectionEnvelope):
    """The event stands, with corrected details (for example, a reassigned scorer)."""

    kind: Literal["EVENT_AMENDED"]
    changes: Amendment


Correction = Annotated[EventVoided | EventAmended, Field(discriminator="kind")]
"""Any correction, discriminated by `kind`."""

CORRECTION_ADAPTER: TypeAdapter[Correction] = TypeAdapter(Correction)


def parse_correction(raw: object) -> Correction:
    """Validate raw wire data (a dict from JSON) into its concrete correction model."""
    return CORRECTION_ADAPTER.validate_python(raw)
