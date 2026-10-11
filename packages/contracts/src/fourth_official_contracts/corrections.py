"""Corrections: the source of truth changed after events were published.

A VAR decision can void a goal; the accreditation panel can reassign its scorer. The pipeline
must find and fix everything it already published from the original event.

Extension rule: every correction shares `CorrectionBase` (identity, match, reason, time). Kinds
that target an event add `EventTargeting`; a future kind that targets something else (for
example a provider restating a metric) adds its own target fields and joins the `Correction`
union with a new `kind`.
"""

from typing import Annotated, Any, Literal

from pydantic import (
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    TypeAdapter,
    model_serializer,
    model_validator,
)

from fourth_official_contracts.primitives import (
    EventId,
    MatchClock,
    MatchId,
    PlayerId,
    UtcTimestamp,
    Version,
    WireModel,
    match_of,
)

CorrectionId = Annotated[str, StringConstraints(pattern=r"^c-[0-9]{4,9}$")]
CorrectionReason = Literal[
    "VAR_OFFSIDE",
    "VAR_FOUL",
    "VAR_HANDBALL",
    "ACCREDITATION_PANEL",
    "PROVIDER_RESTATEMENT",
]
CardKind = Literal["yellow", "second_yellow", "red"]


class CorrectionBase(WireModel):
    """Identity and provenance shared by every correction."""

    correction_id: CorrectionId
    match_id: MatchId
    reason: CorrectionReason
    issued_at: UtcTimestamp


class EventTargeting(CorrectionBase):
    """A correction to one event of the match."""

    target_event_id: EventId
    # The corrected event's new version (2 for a first correction, 3 for a second, ...).
    # Consumers must still apply versions in order; the contract cannot see earlier ones.
    new_version: Annotated[Version, Field(ge=2)]

    @model_validator(mode="after")
    def _target_belongs_to_match(self) -> "EventTargeting":
        if match_of(self.target_event_id) != self.match_id:
            raise ValueError(
                f"event {self.target_event_id} does not belong to match {self.match_id}"
            )
        return self


class EventVoided(EventTargeting):
    """The event no longer stands (for example, a goal disallowed by VAR)."""

    kind: Literal["EVENT_VOIDED"]


_GOAL_FIELDS = frozenset({"scorer_id", "assist_id", "own_goal"})
# Only an assist can be removed outright; every other changed fact needs a value.
_NULLABLE_FIELDS = frozenset({"assist_id"})


class Amendment(WireModel):
    """Fields of the target event that change. Only the fields present on the wire change."""

    scorer_id: PlayerId | None = None
    assist_id: PlayerId | None = None
    own_goal: bool | None = None
    card: CardKind | None = None
    clock: MatchClock | None = None

    @model_validator(mode="after")
    def _changes_are_coherent(self) -> "Amendment":
        changed = self.model_fields_set
        if not changed:
            raise ValueError("an amendment must change at least one field")
        for name in changed - _NULLABLE_FIELDS:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be changed to null")
        if "card" in changed and changed & _GOAL_FIELDS:
            raise ValueError("one amendment cannot change both goal credit and a card")
        return self

    @model_serializer(mode="wrap")
    def _only_changed_fields(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        # Absent means "unchanged" and `assistId: null` means "remove the assist", so every dump
        # path (to_wire, model_dump, model_dump_json) writes only the fields that were set.
        dumped: dict[str, Any] = handler(self)
        fields = type(self).model_fields
        keep = {key for name in self.model_fields_set for key in (name, fields[name].alias)}
        return {key: value for key, value in dumped.items() if key in keep}


class EventAmended(EventTargeting):
    """The event stands, with corrected details (for example, a reassigned scorer)."""

    kind: Literal["EVENT_AMENDED"]
    changes: Amendment


Correction = Annotated[EventVoided | EventAmended, Field(discriminator="kind")]
"""Any correction, discriminated by `kind`."""

CORRECTION_ADAPTER: TypeAdapter[Correction] = TypeAdapter(
    Correction, config=ConfigDict(hide_input_in_errors=True)
)


def parse_correction(raw: object) -> Correction:
    """Validate decoded wire data (a dict from JSON, camelCase keys) into its correction model.

    The `parse_*` functions are the boundary entry points: they accept camelCase keys only.
    Constructing models by field name is for trusted Python code.
    """
    return CORRECTION_ADAPTER.validate_python(raw, by_alias=True, by_name=False)


def parse_correction_json(data: str | bytes) -> Correction:
    """Validate JSON text from the wire into its correction model."""
    return CORRECTION_ADAPTER.validate_json(data, by_alias=True, by_name=False)
