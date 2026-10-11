"""The live feed: what a match replay publishes, in order, for the control room and broadcasters.

Every entry carries its position in the feed (`entrySeq`), so a client can resume where it left off.
Insight entries carry text already rendered by code from the verified insight, so a client shows
it as plain text and never renders references or computes anything itself.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.corrections import Correction
from fourth_official_contracts.insights import Insight
from fourth_official_contracts.localized import LocalizedInsight
from fourth_official_contracts.moments import Moment
from fourth_official_contracts.overlays import LowerThird, OverlaySpec
from fourth_official_contracts.primitives import MatchClock, MatchId, Score, Seq, WireModel
from fourth_official_contracts.tenants import (
    NARRATIVE_KINDS,
    TEMPLATE_FOR,
    Approval,
    ItemKind,
    TenantId,
)
from fourth_official_contracts.verdicts import FindingCode, Verdict

EntrySeq = Annotated[int, Field(ge=1, le=1_000_000)]
# Text for the fourth official's LED board: characters the board can light, kept short.
BoardText = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9 :.,+'%/$-]{1,12}$")]
MAX_ATTEMPTS = 99


class AttemptRecord(WireModel):
    """One try at explaining a moment: who drafted, and how it ended."""

    number: Annotated[int, Field(ge=1, le=MAX_ATTEMPTS)]
    agent: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z-]{1,31}$")]
    model: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")]
    outcome: Literal["passed", "failed", "error"]
    findings: Annotated[tuple[FindingCode, ...], Field(max_length=64, strict=False)]
    # The kind of failure (an exception class name) when the model itself failed.
    error: Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9]{0,63}$")] | None


class RenderedInsight(WireModel):
    """The insight as a viewer reads it: plain text, rendered by code from the references."""

    headline: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    claims: Annotated[tuple[str, ...], Field(min_length=1, max_length=5, strict=False)]


class FeedEntryBase(WireModel):
    entry_seq: EntrySeq
    match_id: MatchId


class ClockEntry(FeedEntryBase):
    """The match clock and score as published so far (corrections in force applied)."""

    kind: Literal["clock"]
    as_of_seq: Seq
    clock: MatchClock
    score: Score


class MomentEntry(FeedEntryBase):
    kind: Literal["moment"]
    moment: Moment

    @model_validator(mode="after")
    def _same_match(self) -> "MomentEntry":
        if self.moment.match_id != self.match_id:
            raise ValueError("the moment belongs to another match")
        return self


class InsightEntry(FeedEntryBase):
    """A verified insight, its verdict, its rendered text and how it was reached."""

    kind: Literal["insight"]
    insight: Insight
    verdict: Verdict
    rendered: RenderedInsight
    attempts: Annotated[
        tuple[AttemptRecord, ...], Field(min_length=1, max_length=MAX_ATTEMPTS, strict=False)
    ]

    @model_validator(mode="after")
    def _verified_and_consistent(self) -> "InsightEntry":
        if self.insight.match_id != self.match_id:
            raise ValueError("the insight belongs to another match")
        if not self.verdict.passed or self.verdict.insight_id != self.insight.insight_id:
            raise ValueError("only an insight with its own passing verdict is published")
        if len(self.rendered.claims) != len(self.insight.claims):
            raise ValueError("every claim is rendered, and only those")
        if self.attempts[-1].outcome != "passed":
            raise ValueError("the last attempt is the one that passed")
        return self


class CorrectionEntry(FeedEntryBase):
    kind: Literal["correction"]
    correction: Correction
    # What changed, in words, rendered by code from the correction and the squad lists.
    summary: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    # What went out and what came in, for the OUT/IN board: the score for a void, the scorer's
    # club and shirt for a reassignment.
    out_text: BoardText
    in_text: BoardText

    @model_validator(mode="after")
    def _same_match(self) -> "CorrectionEntry":
        if self.correction.match_id != self.match_id:
            raise ValueError("the correction belongs to another match")
        return self


class TenantItemEntry(FeedEntryBase):
    """One item for one partner: its graphic, and for narrative items the words in its voice.

    Feeds are filtered by partner at the API, so an entry carries exactly one partner's item."""

    kind: Literal["tenant_item"]
    tenant_id: TenantId
    item_kind: ItemKind
    # Whether the partner's policy has a named editor decide on this item before it airs.
    approval_required: bool
    # Pending and rejected items stay off air.
    state: Literal["on_air", "pending_approval", "rejected"]
    localized: LocalizedInsight | None
    rendered: RenderedInsight | None
    overlay: OverlaySpec
    attempts: Annotated[tuple[AttemptRecord, ...], Field(max_length=MAX_ATTEMPTS, strict=False)]
    approval: Approval | None

    @model_validator(mode="after")
    def _one_partner_and_consistent(self) -> "TenantItemEntry":
        if self.overlay.tenant_id != self.tenant_id:
            raise ValueError("the graphic belongs to another partner")
        if self.overlay.content.template != TEMPLATE_FOR[self.item_kind]:
            raise ValueError(f"{self.item_kind} items are shown as {TEMPLATE_FOR[self.item_kind]}")
        if self.item_kind in NARRATIVE_KINDS:
            self._check_narrative()
        else:
            self._check_data()
        self._check_approval()
        return self

    def _check_narrative(self) -> None:
        localized, rendered, content = self.localized, self.rendered, self.overlay.content
        if localized is None or rendered is None or not self.attempts:
            raise ValueError("a narrative item carries its words and how they were reached")
        if localized.tenant_id != self.tenant_id or localized.match_id != self.match_id:
            raise ValueError("the words belong to another partner or match")
        if localized.item_id != self.overlay.item_id:
            raise ValueError("the graphic shows another item")
        if len(rendered.claims) != len(localized.claims):
            raise ValueError("every claim is rendered, and only those")
        if self.attempts[-1].outcome != "passed":
            raise ValueError("the last attempt is the one that passed")
        if not isinstance(content, LowerThird) or (content.headline, content.line) != (
            rendered.headline,
            rendered.claims[0],
        ):
            raise ValueError("the graphic shows exactly the words rendered for the item")
        disclosure = self.overlay.disclosure
        if disclosure is None or disclosure.reason == "data":
            raise ValueError("words written by agents are always disclosed as such")

    def _check_data(self) -> None:
        if self.localized is not None or self.rendered is not None or self.attempts:
            raise ValueError("a data item carries no words written by an agent")
        disclosure = self.overlay.disclosure
        if disclosure is not None and disclosure.reason != "data":
            raise ValueError("a data item is not disclosed as written by agents")

    def _check_approval(self) -> None:
        decision = None if self.approval is None else self.approval.decision
        if self.state == "pending_approval" and (not self.approval_required or decision):
            raise ValueError("only an item awaiting a required decision is pending")
        if self.state == "rejected" and decision != "rejected":
            raise ValueError("a rejected item records the editor's rejection")
        if self.state == "on_air" and (
            decision == "rejected" or (self.approval_required and decision != "approved")
        ):
            raise ValueError("an item that needs approval airs only once approved")
        disclosure = self.overlay.disclosure
        reviewed = disclosure is not None and disclosure.reason == "ai_assisted_reviewed"
        if reviewed and decision != "approved":
            raise ValueError("a reviewed label needs the approval behind it")


FeedEntry = Annotated[
    ClockEntry | MomentEntry | InsightEntry | CorrectionEntry | TenantItemEntry,
    Field(discriminator="kind"),
]
FEED_ENTRY_ADAPTER: TypeAdapter[FeedEntry] = TypeAdapter(FeedEntry)


def parse_feed_entry(raw: object) -> FeedEntry:
    """Validate decoded wire data (camelCase keys only) into a feed entry."""
    return FEED_ENTRY_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
