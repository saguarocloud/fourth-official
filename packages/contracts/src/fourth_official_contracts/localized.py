"""A verified insight in one partner's voice: same claims, same evidence, new words.

The Localizer rewrites only the text. The evidence and claim types are copied from the canonical
insight by code, and the Verifier checks that every reference survived, so a localised item can
never cite or state anything the canonical one did not.
"""

from typing import Annotated

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.insights import (
    MAX_CLAIMS,
    Claim,
    HeadlineText,
    InsightId,
    Provenance,
    claim_references,
    insight_id_for,
    single_line,
)
from fourth_official_contracts.moments import MomentId
from fourth_official_contracts.primitives import MatchId, Seq, Version, WireModel, match_of
from fourth_official_contracts.tenants import TENANT_LOCALES, Locale, TenantId

ItemId = Annotated[
    str, StringConstraints(max_length=128, pattern=r"^it-[a-z]+(-[a-z]+)*-[A-Za-z0-9_-]{1,100}$")
]


def item_id_for(tenant_id: str, insight_id: str, *, version: int) -> str:
    """A localised item is named after its partner, its canonical insight and its version."""
    return f"it-{tenant_id}-{insight_id}-v{version}"


class LocalizedInsight(WireModel):
    item_id: ItemId
    tenant_id: TenantId
    locale: Locale
    # The canonical insight this rewrites, and the moment and match it is about.
    insight_id: InsightId
    match_id: MatchId
    moment_id: MomentId
    as_of_seq: Seq
    version: Version
    headline: HeadlineText
    claims: Annotated[tuple[Claim, ...], Field(min_length=1, max_length=MAX_CLAIMS, strict=False)]
    provenance: Provenance
    # The policy version it was written under.
    policy_version: Version

    @model_validator(mode="after")
    def _identity_and_claims_are_consistent(self) -> "LocalizedInsight":
        if self.locale != TENANT_LOCALES[self.tenant_id]:
            raise ValueError(f"{self.tenant_id} broadcasts in {TENANT_LOCALES[self.tenant_id]}")
        if self.item_id != item_id_for(self.tenant_id, self.insight_id, version=self.version):
            raise ValueError("the item id names another partner, insight or version")
        attempt = int(self.insight_id.rsplit("-a", 1)[1])
        if self.insight_id != insight_id_for(self.moment_id, attempt=attempt):
            raise ValueError(f"insight {self.insight_id} is not about moment {self.moment_id}")
        if not self.moment_id.startswith(f"mo-{self.match_id}-"):
            raise ValueError(f"moment {self.moment_id} belongs to another match")
        ids = [c.claim_id for c in self.claims]
        if len(set(ids)) != len(ids):
            raise ValueError("claim ids must be unique")
        for claim in self.claims:
            if any(match_of(e) != self.match_id for e in claim.evidence.event_ids):
                raise ValueError(f"claim {claim.claim_id} cites an event from another match")
        single_line(self.headline)
        cited = {s for c in self.claims for s in c.evidence.metric_snapshot_ids}
        for kind, argument in claim_references(self.headline):
            if kind == "value" and argument not in cited:
                raise ValueError(f"headline value {argument} is not cited by any claim")
        return self


LOCALIZED_INSIGHT_ADAPTER: TypeAdapter[LocalizedInsight] = TypeAdapter(LocalizedInsight)


def parse_localized_insight(raw: object) -> LocalizedInsight:
    """Validate decoded wire data (camelCase keys only) into a localised insight."""
    return LOCALIZED_INSIGHT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
