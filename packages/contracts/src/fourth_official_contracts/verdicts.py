"""Verdicts: the deterministic Verifier's decision on an insight, and every reason for it.

A verdict is shown in the evidence drawer and kept in the provenance record. On failure its
findings go back to the Analyst as structured feedback.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.primitives import MatchId, WireModel

FindingCode = Literal[
    # The insight is not about the moment it claims to explain.
    "MOMENT_MISMATCH",
    # The draft could not be built into a valid insight (malformed markup, missing evidence...).
    "MALFORMED_INSIGHT",
    # A number or a name written as text instead of rendered from evidence.
    "UNSUPPORTED_CHARACTER",
    "BARE_NUMBER",
    "RAW_NAME",
    "UNVERIFIED_NAME",
    "UNKNOWN_WORD",
    "FUTURE_WORDING",
    # A reference that does not resolve in the match.
    "UNKNOWN_PLAYER",
    "UNKNOWN_CLUB",
    # A player or minute named that the cited events do not show.
    "PLAYER_NOT_IN_EVIDENCE",
    "MINUTE_NOT_IN_EVIDENCE",
    "SNAPSHOT_NOT_FOUND",
    "UNDEFINED_VALUE",
    "EVIDENCE_NOT_FOUND",
    # Evidence the insight was not allowed to use.
    "FUTURE_EVIDENCE",
    "FUTURE_MINUTE",
    "VOIDED_EVIDENCE",
    "SUPERSEDED_EVIDENCE",
]
MAX_FINDINGS = 64


class Finding(WireModel):
    # None when the finding is about the headline or the insight as a whole.
    claim_id: Annotated[str, StringConstraints(pattern=r"^cl-[0-9]{1,3}$")] | None
    code: FindingCode
    detail: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class Verdict(WireModel):
    insight_id: Annotated[str, StringConstraints(max_length=72, pattern=r"^in-m[0-9]{1,12}-")]
    match_id: MatchId
    passed: bool
    findings: Annotated[tuple[Finding, ...], Field(max_length=MAX_FINDINGS, strict=False)]

    @model_validator(mode="after")
    def _passes_only_without_findings(self) -> "Verdict":
        if self.passed == bool(self.findings):
            raise ValueError("a verdict passes only without findings, and fails only with them")
        if not self.insight_id.startswith(f"in-{self.match_id}-"):
            raise ValueError(f"insight {self.insight_id} belongs to another match")
        return self


# The model's own config already hides input in validation errors.
VERDICT_ADAPTER: TypeAdapter[Verdict] = TypeAdapter(Verdict)


def parse_verdict(raw: object) -> Verdict:
    """Validate decoded wire data (camelCase keys only) into a verdict."""
    return VERDICT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
