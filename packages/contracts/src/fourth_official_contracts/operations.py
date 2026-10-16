"""Operations: what the platform measured while it ran, for the Operations screen and the
Control Room.

Like the scorecard, every measure is kept as counts and durations, never as a ready-made
percentage, so a reader computes a rate the same way everywhere and nothing stored can drift from
its counts. Durations are wall-clock milliseconds measured by the platform itself, and every
percentile is computed by code from the measured durations (nearest rank). Money is whole
micro-dollars (millionths of a US dollar), priced by code from tokens and the report's own pricing
(docs/cost-model.md).
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.primitives import MatchId, UtcTimestamp, WireModel
from fourth_official_contracts.scorecard import Count, Ratio
from fourth_official_contracts.tenants import TenantId

MAX_MATCHES = 100
MAX_PARTNERS = 8
# An hour: no measured duration of a running match is longer.
Millis = Annotated[int, Field(ge=0, le=3_600_000)]
# Tokens and micro-dollars: a matchday's worth, with room to spare.
Amount = Annotated[int, Field(ge=0, le=1_000_000_000)]
ModelAlias = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")]
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


class TokenUse(WireModel):
    """Tokens model calls spent, as the service reported them."""

    input: Amount
    output: Amount


class PartnerOperations(WireModel):
    """One partner's items in one match: how many it published, how many it held for its editor,
    and, for the ones it aired without one, how long from the event to air."""

    tenant_id: TenantId
    items: Count
    # Items held for an editor when they were published (approved later or not).
    held: Count
    on_air: Spread
    # Items aired without an editor that went on air within the on-air target.
    within_target: Ratio
    # What the Localizer spent writing this partner's items, and what that cost.
    tokens: TokenUse
    cost_microusd: Amount
    # The partner's own latency budget (its policy, at the time of the report), and the items
    # aired without an editor that went on air within it; none when the budget is not known.
    latency_budget_ms: Millis | None
    within_budget: Ratio

    @model_validator(mode="after")
    def _items_add_up(self) -> "PartnerOperations":
        if self.held > self.items:
            raise ValueError("a partner cannot have held more items than it published")
        if self.on_air.count != self.within_target.of or self.on_air.count > self.items:
            raise ValueError("the items timed are the items aired, and no more than published")
        judged = 0 if self.latency_budget_ms is None else self.on_air.count
        if self.within_budget.of != judged:
            raise ValueError("the items judged against the budget are the items timed, if any")
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
    # Event to on air, every partner's items in this match pooled.
    on_air: Spread
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
    # Every model call of the match (the Analyst's and the Localizer's), what they cost, and the
    # match's share of the platform's infrastructure for as long as it ran.
    tokens: TokenUse
    model_cost_microusd: Amount
    infra_cost_microusd: Amount
    partners: Annotated[tuple[PartnerOperations, ...], Field(max_length=MAX_PARTNERS, strict=False)]

    @model_validator(mode="after")
    def _one_entry_per_partner(self) -> "MatchOperations":
        tenants = [p.tenant_id for p in self.partners]
        if len(set(tenants)) != len(tenants):
            raise ValueError("each partner is reported once per match")
        if sum(p.cost_microusd for p in self.partners) > self.model_cost_microusd:
            raise ValueError("the partners' model cost is part of the match's, never more")
        if (
            sum(p.tokens.input for p in self.partners) > self.tokens.input
            or sum(p.tokens.output for p in self.partners) > self.tokens.output
        ):
            raise ValueError("the partners' tokens are part of the match's, never more")
        if self.on_air.count != sum(p.on_air.count for p in self.partners):
            raise ValueError("a match times its partners' items, and only those")
        if self.first_pass.of > self.fallbacks.of or self.explain.count > self.fallbacks.of:
            raise ValueError("first passes and explanations are among the insights published")
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


class ModelPrice(WireModel):
    """What a model deployment's tokens cost, in micro-dollars per million tokens."""

    model: ModelAlias
    input_microusd_per_million: Amount
    output_microusd_per_million: Amount


class Pricing(WireModel):
    """The prices the report's costs were computed with."""

    models: Annotated[tuple[ModelPrice, ...], Field(max_length=8, strict=False)]
    infra_microusd_per_hour: Amount

    @model_validator(mode="after")
    def _each_model_once(self) -> "Pricing":
        names = [m.model for m in self.models]
        if len(set(names)) != len(names):
            raise ValueError("each model is priced once")
        return self


class OperationsReport(WireModel):
    """The matchday's operations: objectives, the error budget, and each match."""

    generated_at: UtcTimestamp
    objectives: Annotated[tuple[Objective, ...], Field(max_length=8, strict=False)]
    budget: ErrorBudget
    # Event to on air, every partner in every match.
    on_air: Spread
    matches: Annotated[tuple[MatchOperations, ...], Field(max_length=MAX_MATCHES, strict=False)]
    pricing: Pricing

    @model_validator(mode="after")
    def _each_once(self) -> "OperationsReport":
        keys = [o.key for o in self.objectives]
        if len(set(keys)) != len(keys):
            raise ValueError("each objective is reported once")
        matches = [m.match_id for m in self.matches]
        if len(set(matches)) != len(matches):
            raise ValueError("each match is reported once")
        if self.budget.of != self.on_air.count:
            raise ValueError("the error budget counts the items timed on air")
        pooled = {"on_air_p50": self.on_air.p50_ms, "on_air_p95": self.on_air.p95_ms}
        if any(o.key in pooled and o.measured_ms != pooled[o.key] for o in self.objectives):
            raise ValueError("the on-air objectives report the pooled percentiles")
        if self.on_air.count != sum(p.on_air.count for m in self.matches for p in m.partners):
            raise ValueError("the pooled items are every match's partners' items")
        return self


OPERATIONS_REPORT_ADAPTER: TypeAdapter[OperationsReport] = TypeAdapter(OperationsReport)


def parse_operations_report(raw: object) -> OperationsReport:
    """Validate decoded wire data (camelCase keys only) into an operations report."""
    return OPERATIONS_REPORT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
