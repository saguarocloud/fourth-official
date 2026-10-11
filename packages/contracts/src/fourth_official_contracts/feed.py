"""The live feed: what a match replay publishes, in order, for the control room and broadcasters.

Every entry carries its position in the feed (`entrySeq`), so a client can resume where it left off.
Insight entries carry text already rendered by code from the verified insight, so a client shows
it as plain text and never renders references or computes anything itself.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.corrections import Correction
from fourth_official_contracts.insights import Insight
from fourth_official_contracts.moments import Moment
from fourth_official_contracts.primitives import MatchClock, MatchId, Score, Seq, WireModel
from fourth_official_contracts.verdicts import FindingCode, Verdict

EntrySeq = Annotated[int, Field(ge=1, le=1_000_000)]
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

    @model_validator(mode="after")
    def _same_match(self) -> "CorrectionEntry":
        if self.correction.match_id != self.match_id:
            raise ValueError("the correction belongs to another match")
        return self


FeedEntry = Annotated[
    ClockEntry | MomentEntry | InsightEntry | CorrectionEntry, Field(discriminator="kind")
]
FEED_ENTRY_ADAPTER: TypeAdapter[FeedEntry] = TypeAdapter(FeedEntry)


def parse_feed_entry(raw: object) -> FeedEntry:
    """Validate decoded wire data (camelCase keys only) into a feed entry."""
    return FEED_ENTRY_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
