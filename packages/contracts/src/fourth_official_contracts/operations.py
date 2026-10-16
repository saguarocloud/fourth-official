"""Operations: what the platform measured while it ran, for the Operations screen and the
Control Room.

Like the scorecard, every measure is kept as counts and durations, never as a ready-made
percentage, so a reader computes a rate the same way everywhere and nothing stored can drift from
its counts. Durations are wall-clock milliseconds measured by the platform itself, and every
percentile is computed by code from the measured durations (nearest rank).
"""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from fourth_official_contracts.primitives import MatchId, UtcTimestamp, WireModel
from fourth_official_contracts.scorecard import Count, Ratio
from fourth_official_contracts.tenants import TenantId

MAX_MATCHES = 100
MAX_PARTNERS = 8
# An hour: no measured duration of a running match is longer.
Millis = Annotated[int, Field(ge=0, le=3_600_000)]
ObjectiveKey = Literal["on_air_p50", "on_air_p95", "correction_p95"]
MatchState = Literal["idle", "running", "finished", "failed"]


class Spread(WireModel):
    """How many durations were measured, and their median and 95th percentile."""

    count: Count
    p50_ms: Millis | None
    p95_ms: Millis | None

    @model_validator(mode="after")
    def _percentiles_of_what_was_measured(self) -> "Spread":
        if (self.count == 0) != (self.p50_ms is None) or (self.count == 0) != (self.p95_ms is None):
            raise ValueError("percentiles are given exactly when something was measured")
        if self.p50_ms is not None and self.p95_ms is not None and self.p50_ms > self.p95_ms:
            raise ValueError("the median is never above the 95th percentile")
        return self


class PartnerOperations(WireModel):
    """One partner's items in one match: how many it published, how many it held for its editor,
    and, for the ones it aired without one, how long from the event to air."""

    tenant_id: TenantId
    items: Count
    held: Count
    on_air: Spread
    # Items aired without an editor that went on air within the on-air target.
    within_target: Ratio

    @model_validator(mode="after")
    def _items_add_up(self) -> "PartnerOperations":
        if self.held > self.items:
            raise ValueError("a partner cannot have held more items than it published")
        if self.on_air.count != self.within_target.of or self.on_air.count > self.items:
            raise ValueError("the items timed are the items aired, and no more than published")
        return self


class MatchOperations(WireModel):
    """One match of the current matchday run."""

    match_id: MatchId
    state: MatchState
    # How long the run has taken so far, or took.
    run_ms: Millis
    events_played: Count
    moments: Count
    # From a moment being published to its verified insight being published.
    explain: Spread
    # Insights whose first model draft passed the Verifier, of insights a model drafted.
    first_pass: Ratio
    # Insights the deterministic template wrote, of insights published.
    fallbacks: Ratio
    # Model drafts the Verifier passed, of model drafts it judged.
    model_drafts: Ratio
    # Attempts where the model itself failed (a timeout or a service error).
    model_errors: Count
    # How long the corrections desk took over each correction.
    corrections: Spread
    corrected_items: Count
    partners: Annotated[tuple[PartnerOperations, ...], Field(max_length=MAX_PARTNERS, strict=False)]

    @model_validator(mode="after")
    def _one_entry_per_partner(self) -> "MatchOperations":
        tenants = [p.tenant_id for p in self.partners]
        if len(set(tenants)) != len(tenants):
            raise ValueError("each partner is reported once per match")
        return self


class Objective(WireModel):
    """A service level objective: its target and what was measured against it."""

    key: ObjectiveKey
    target_ms: Millis
    measured_ms: Millis | None


class ErrorBudget(WireModel):
    """The on-air objective as a share of items: `within_percent` of items aired without an
    editor go on air within `target_ms`. Items later than that spend the budget."""

    within_percent: Annotated[int, Field(ge=1, le=100)]
    target_ms: Millis
    late: Count
    of: Count

    @model_validator(mode="after")
    def _late_items_were_measured(self) -> "ErrorBudget":
        if self.late > self.of:
            raise ValueError("there cannot be more late items than items measured")
        return self


class OperationsReport(WireModel):
    """The matchday's operations: objectives, the error budget, and each match."""

    generated_at: UtcTimestamp
    objectives: Annotated[tuple[Objective, ...], Field(max_length=8, strict=False)]
    budget: ErrorBudget
    # Event to on air, every partner in every match.
    on_air: Spread
    matches: Annotated[tuple[MatchOperations, ...], Field(max_length=MAX_MATCHES, strict=False)]

    @model_validator(mode="after")
    def _each_once(self) -> "OperationsReport":
        keys = [o.key for o in self.objectives]
        if len(set(keys)) != len(keys):
            raise ValueError("each objective is reported once")
        matches = [m.match_id for m in self.matches]
        if len(set(matches)) != len(matches):
            raise ValueError("each match is reported once")
        return self


OPERATIONS_REPORT_ADAPTER: TypeAdapter[OperationsReport] = TypeAdapter(OperationsReport)


def parse_operations_report(raw: object) -> OperationsReport:
    """Validate decoded wire data (camelCase keys only) into an operations report."""
    return OPERATIONS_REPORT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
