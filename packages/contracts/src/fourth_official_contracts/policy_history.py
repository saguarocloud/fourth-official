"""A partner's policy history: every version, in order, and who changed what, when and why.

Policy Studio edits a partner's policy by writing its next version; nothing is overwritten. The
demo has no sign-in, so a change is recorded against the partner's duty editor, a named demo
identity, as an editor's decision is (ADR-011).
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.insights import single_line
from fourth_official_contracts.primitives import UtcTimestamp, Version, WireModel
from fourth_official_contracts.tenants import EditorName, TenantId, TenantPolicy

MAX_VERSIONS = 500

# A policy's fields as they travel (camelCase), the ones a change can name.
PolicyField = Literal[
    "displayName",
    "tone",
    "preferTerms",
    "avoidTerms",
    "blockedTopics",
    "approvalRequired",
    "disclosureMode",
    "latencyBudgetMs",
    "maxItemsPerMinute",
    "templates",
    "correctionBehaviour",
]


def _one_line(text: str) -> str:
    single_line(text)
    return text


Reason = Annotated[str, StringConstraints(min_length=1, max_length=200), AfterValidator(_one_line)]


class PolicyChange(WireModel):
    """How one version came to be."""

    tenant_id: TenantId
    version: Version
    # bundled: shipped with the release; edited: in Policy Studio; reset: back to the release's.
    action: Literal["bundled", "edited", "reset"]
    editor: EditorName
    changed_at: UtcTimestamp
    reason: Reason
    fields: Annotated[tuple[PolicyField, ...], Field(max_length=16, strict=False)]


class PolicyHistory(WireModel):
    """Every version of one partner's policy, oldest first, each with the change that made it."""

    tenant_id: TenantId
    versions: Annotated[
        tuple[TenantPolicy, ...], Field(min_length=1, max_length=MAX_VERSIONS, strict=False)
    ]
    changes: Annotated[
        tuple[PolicyChange, ...], Field(min_length=1, max_length=MAX_VERSIONS, strict=False)
    ]

    @model_validator(mode="after")
    def _consistent(self) -> "PolicyHistory":
        if len(self.versions) != len(self.changes):
            raise ValueError("every version needs the change that made it")
        for number, (policy, change) in enumerate(
            zip(self.versions, self.changes, strict=True), start=1
        ):
            if policy.version != number or change.version != number:
                raise ValueError(f"versions run from 1 without gaps; expected {number}")
            if self.tenant_id != policy.tenant_id or self.tenant_id != change.tenant_id:
                raise ValueError("a history holds one partner's policy only")
        return self

    @property
    def current(self) -> TenantPolicy:
        return self.versions[-1]


POLICY_HISTORY_ADAPTER: TypeAdapter[PolicyHistory] = TypeAdapter(PolicyHistory)


def parse_policy_history(raw: object) -> PolicyHistory:
    """Validate decoded wire data (camelCase keys only) into a policy history."""
    return POLICY_HISTORY_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
