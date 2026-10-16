"""A partner item's provenance record, built from what the feed says about it."""

from collections.abc import Sequence
from datetime import datetime

from fourth_official_contracts import (
    InsightEntry,
    ProvenanceClaim,
    ProvenanceRecord,
    SignedAttempt,
    TenantItemEntry,
)

ISSUER = "Meridian League Studios"


def record_for(
    item: TenantItemEntry,
    canonical: InsightEntry | None,
    *,
    issued_at: datetime,
    corrections: Sequence[str],
) -> ProvenanceRecord | None:
    """The record of a narrative item's latest version: None for a graphic no agent wrote (a
    correction strap or the score bug), which carries no words to account for."""
    localized, rendered = item.localized, item.rendered
    if localized is None or rendered is None:
        return None
    return ProvenanceRecord(
        item_id=item.overlay.item_id,
        tenant_id=item.tenant_id,
        match_id=item.match_id,
        insight_id=localized.insight_id,
        version=localized.version,
        locale=localized.locale,
        state=item.state,
        issuer=ISSUER,
        issued_at=issued_at,
        feed_entry=item.entry_seq,
        headline=rendered.headline,
        claims=tuple(
            ProvenanceClaim(text=text, evidence=claim.evidence)
            for text, claim in zip(rendered.claims, localized.claims, strict=True)
        ),
        canonical=canonical.insight.provenance if canonical else None,
        localized=localized.provenance,
        attempts=tuple(SignedAttempt.of(a) for a in item.attempts),
        disclosure=item.overlay.disclosure,
        approval=item.approval,
        supersedes=item.overlay.supersedes,
        corrections=tuple(corrections),
    )
