"""What a model writes: an insight draft. Code, not the model, turns it into an `Insight`.

The draft is the model's structured output. It holds only what the model decides (wording,
claim types, which evidence to cite); identity, the moment and provenance are added by code.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from fourth_official_contracts import (
    Claim,
    Evidence,
    Insight,
    Moment,
    Provenance,
    insight_id_for,
)


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["stat", "comparison", "causal", "milestone"]
    text: str = Field(description="One sentence. Every number, name and minute is a reference.")
    event_ids: list[str] = Field(description="Event IDs this claim rests on")
    snapshot_ids: list[str] = Field(description="Metric snapshot IDs this claim quotes")


class InsightDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    headline: str = Field(description="A short headline, with references for names and numbers")
    claims: list[ClaimDraft] = Field(description="One to five claims, each with its evidence")


def to_insight(
    draft: InsightDraft, moment: Moment, *, attempt: int, provenance: Provenance
) -> Insight:
    """Build the insight the draft describes. Raises pydantic's `ValidationError` if the draft
    breaks the contract (malformed markup, a claim without evidence, too many claims...)."""
    return Insight(
        insight_id=insight_id_for(moment.moment_id, attempt=attempt),
        match_id=moment.match_id,
        moment_id=moment.moment_id,
        as_of_seq=moment.as_of_seq,
        locale="en",
        headline=draft.headline,
        claims=tuple(
            Claim(
                claim_id=f"cl-{n}",
                type=claim.type,
                text=claim.text,
                evidence=Evidence(
                    event_ids=tuple(claim.event_ids), metric_snapshot_ids=tuple(claim.snapshot_ids)
                ),
            )
            for n, claim in enumerate(draft.claims, start=1)
        ),
        provenance=provenance,
    )
