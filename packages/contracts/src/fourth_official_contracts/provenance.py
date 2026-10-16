"""Provenance: how a partner's item came to be, signed by the studio.

A record names the item and its version, its words and the evidence each claim rests on, who and
what wrote it (the canonical insight and the partner's version), every attempt, how it is
disclosed, the editor's decision, what it replaces, and the corrections that reached it. Its
canonical bytes (sorted keys, no spaces, UTF-8) are hashed and the hash is signed, so a record
changed after it was issued no longer verifies.
"""

import json
import re
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.corrections import CorrectionId
from fourth_official_contracts.feed import MAX_ATTEMPTS, AttemptRecord, EntrySeq
from fourth_official_contracts.insights import Evidence, InsightId, Provenance, single_line
from fourth_official_contracts.localized import ItemId
from fourth_official_contracts.primitives import MatchId, UtcTimestamp, Version, WireModel
from fourth_official_contracts.tenants import (
    TENANT_LOCALES,
    Approval,
    Disclosure,
    Locale,
    TenantId,
)
from fourth_official_contracts.verdicts import FindingCode

Line = Annotated[str, StringConstraints(min_length=1, max_length=300)]


class ProvenanceClaim(WireModel):
    """A claim as the audience read it, and the evidence it rests on."""

    text: Line
    evidence: Evidence


class SignedAttempt(WireModel):
    """An attempt as a record signs it: who drafted and how it ended. What the attempt cost is
    operations, not provenance, and stays out, so a record's signed bytes never change shape."""

    number: Annotated[int, Field(ge=1, le=MAX_ATTEMPTS)]
    agent: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z-]{1,31}$")]
    model: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")]
    outcome: Literal["passed", "failed", "error"]
    findings: Annotated[tuple[FindingCode, ...], Field(max_length=64, strict=False)]
    error: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9]{0,63}$")] | None

    @classmethod
    def of(cls, attempt: AttemptRecord) -> "SignedAttempt":
        return cls(
            number=attempt.number,
            agent=attempt.agent,
            model=attempt.model,
            outcome=attempt.outcome,
            findings=attempt.findings,
            error=attempt.error,
        )


class ProvenanceRecord(WireModel):
    item_id: ItemId
    tenant_id: TenantId
    match_id: MatchId
    insight_id: InsightId
    version: Version
    locale: Locale
    state: Literal["on_air", "pending_approval", "rejected", "retracted", "amended"]
    issuer: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    issued_at: UtcTimestamp
    # Where the item's latest version sits on its match's feed.
    feed_entry: EntrySeq
    headline: Line
    claims: Annotated[tuple[ProvenanceClaim, ...], Field(min_length=1, max_length=8, strict=False)]
    # Who wrote the canonical insight, and who wrote the partner's version of it.
    canonical: Provenance | None
    localized: Provenance
    attempts: Annotated[tuple[SignedAttempt, ...], Field(max_length=MAX_ATTEMPTS, strict=False)]
    disclosure: Disclosure | None
    approval: Approval | None
    supersedes: ItemId | None
    corrections: Annotated[tuple[CorrectionId, ...], Field(max_length=50, strict=False)]

    @model_validator(mode="after")
    def _one_item(self) -> "ProvenanceRecord":
        single_line(self.headline)
        for claim in self.claims:
            single_line(claim.text)
        if self.locale != TENANT_LOCALES[self.tenant_id]:
            raise ValueError(f"{self.tenant_id} broadcasts in {TENANT_LOCALES[self.tenant_id]}")
        stem = re.fullmatch(
            rf"it-{self.tenant_id}-{re.escape(self.insight_id)}-v([0-9]+)", self.item_id
        )
        if stem is None or int(stem.group(1)) != self.version:
            raise ValueError("the record is of the partner's version of the insight")
        if not self.insight_id.startswith(f"in-{self.match_id}-"):
            raise ValueError("the insight belongs to another match")
        return self


class SignedProvenance(WireModel):
    """A record, the SHA-256 of its canonical bytes, and the studio's signature over that hash."""

    record: ProvenanceRecord
    content_hash: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    # Base64url, unpadded.
    signature: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,700}$")]
    # ES256 with the studio's Key Vault key; HS256 with a local key in development and tests.
    algorithm: Literal["ES256", "HS256"]
    key_id: Annotated[str, StringConstraints(min_length=1, max_length=300)]


def canonical_bytes(record: ProvenanceRecord) -> bytes:
    """The bytes that are hashed and signed: the wire form, keys sorted, no spaces, UTF-8."""
    return json.dumps(
        record.to_wire(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


SIGNED_PROVENANCE_ADAPTER: TypeAdapter[SignedProvenance] = TypeAdapter(SignedProvenance)


def parse_signed_provenance(raw: object) -> SignedProvenance:
    """Validate decoded data (camelCase keys only) into a signed provenance record."""
    return SIGNED_PROVENANCE_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
