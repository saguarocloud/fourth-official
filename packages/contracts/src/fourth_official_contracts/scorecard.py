"""The Proving Ground's scorecard and the Release Gate's verdict.

A scorecard is one configuration (prompt versions and model aliases) run over the first N matches
of the seeded benchmark. Every measure is kept as counts, never as a ready-made percentage, so a
reader computes the rate the same way the gate does and nothing stored can drift from its counts.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.insights import ClaimText, single_line
from fourth_official_contracts.localized import ItemId
from fourth_official_contracts.primitives import EventId, MatchId, UtcTimestamp, WireModel

MAX_MATCHES = 100
MAX_FAILURES = 200
MAX_COUNT = 1_000_000

ConfigurationName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")]
# `analyst/v1.2`, `localizer/v1.0`, or `template` for a run that writes without a model.
PromptRef = Annotated[
    str, StringConstraints(pattern=r"^(template|[a-z][a-z-]{1,31}/v[0-9]{1,3}\.[0-9]{1,3})$")
]
ModelAlias = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")]


def _one_line(text: str) -> str:
    single_line(text)
    return text


# Free text a page will show: one line of printable characters, no bidirectional overrides or
# zero-width characters that could disguise it. Readers still render it as text, never as markup.
Reason = Annotated[str, StringConstraints(min_length=1, max_length=200), AfterValidator(_one_line)]
AiredText = Annotated[ClaimText, AfterValidator(_one_line)]
Count = Annotated[int, Field(ge=0, le=MAX_COUNT)]


class Configuration(WireModel):
    """What was run: the prompts the agents used and the model deployments they drafted on."""

    name: ConfigurationName
    analyst_prompt: PromptRef
    localizer_prompt: PromptRef
    models: Annotated[tuple[ModelAlias, ...], Field(max_length=8, strict=False)]


class Ratio(WireModel):
    """`hit` of `of` cases, for example 45 of 50 planted storylines surfaced."""

    hit: Count
    of: Count

    @model_validator(mode="after")
    def _hits_are_cases(self) -> "Ratio":
        if self.hit > self.of:
            raise ValueError("a ratio cannot count more hits than cases")
        return self


class Latency(WireModel):
    p50: Annotated[float, Field(ge=0, le=600_000)]
    p95: Annotated[float, Field(ge=0, le=600_000)]


class Metrics(WireModel):
    # Claims still on air at full time that the ground truth supports, of all such claims.
    supported_claims: Ratio
    # Planted storylines the pipeline surfaced, of those it is built to surface.
    storyline_recall: Ratio
    # Published insights about a key moment (planted, or a goal, red card or VAR decision).
    key_moment_precision: Ratio
    # Deliberately wrong claims the Verifier refused, of those planted.
    verifier_catch: Ratio
    # Partner items on air that break their partner's policy.
    policy_violations: Count
    # Insights a model wrote (the rest fell back to the template).
    model_written: Ratio
    # Model-written insights that passed the Verifier on their first attempt.
    first_attempt_pass: Ratio
    # Partner items resting on a corrected event that the corrections desk pulled or remade.
    corrections_carried: Ratio
    # Time to explain a moment, model calls included; nothing to report without a model.
    latency_ms: Latency | None
    cost_usd: Annotated[float, Field(ge=0, le=10_000)] | None


class FailedClaim(WireModel):
    """A claim on air at full time that the ground truth does not support, and why."""

    match_id: MatchId
    # The partner item that aired it.
    item_id: ItemId
    # `cl-1`, or `headline`.
    claim_id: Annotated[str, StringConstraints(pattern=r"^(cl-[0-9]{1,3}|headline)$")]
    text: AiredText
    event_ids: Annotated[tuple[EventId, ...], Field(max_length=64, strict=False)]
    reasons: Annotated[tuple[Reason, ...], Field(min_length=1, max_length=8, strict=False)]


class Scorecard(WireModel):
    configuration: Configuration
    matches: Annotated[int, Field(ge=1, le=MAX_MATCHES)]
    first_match: MatchId
    generated_at: UtcTimestamp
    metrics: Metrics
    failures: Annotated[tuple[FailedClaim, ...], Field(max_length=MAX_FAILURES, strict=False)]


GateRule = Literal[
    "unsupported_claims",
    "policy_violations",
    "verifier_catch",
    "corrections_carried",
    "storyline_recall",
    "model_written",
    "latency_p95",
]


class GateCheck(WireModel):
    rule: GateRule
    passed: bool
    detail: Reason


class GateVerdict(WireModel):
    """The Release Gate's answer for a candidate against the baseline: allowed only if every
    rule passes."""

    candidate: ConfigurationName
    baseline: ConfigurationName
    allowed: bool
    checks: Annotated[tuple[GateCheck, ...], Field(min_length=1, max_length=16, strict=False)]

    @model_validator(mode="after")
    def _allowed_only_if_every_rule_passes(self) -> "GateVerdict":
        if self.allowed != all(c.passed for c in self.checks):
            raise ValueError("a candidate is allowed exactly when every rule passes")
        return self


SCORECARD_ADAPTER: TypeAdapter[Scorecard] = TypeAdapter(Scorecard)
GATE_VERDICT_ADAPTER: TypeAdapter[GateVerdict] = TypeAdapter(GateVerdict)


def parse_scorecard(raw: object) -> Scorecard:
    """Validate decoded wire data (camelCase keys only) into a scorecard."""
    return SCORECARD_ADAPTER.validate_python(raw, by_alias=True, by_name=False)


def parse_gate_verdict(raw: object) -> GateVerdict:
    """Validate decoded wire data (camelCase keys only) into a gate verdict."""
    return GATE_VERDICT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
