"""The matchday wall: each match as the Control Room shows it (score, clock, who is on air,
what awaits an editor, corrections), the latest partner items, and the latest correction, all
computed by code from the matches' feeds.
"""

import itertools
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from fourth_official_contracts.corrections import CorrectionId
from fourth_official_contracts.feed import EntrySeq
from fourth_official_contracts.operations import MatchState, Millis
from fourth_official_contracts.primitives import (
    ClubCode,
    MatchClock,
    MatchId,
    Score,
    UtcTimestamp,
    WireModel,
)
from fourth_official_contracts.scorecard import Count, Reason
from fourth_official_contracts.tenants import TENANT_LOCALES, TenantId

MAX_MATCHES = 100
MAX_ACTIVITY = 50
ItemState = Literal["on_air", "pending_approval", "rejected", "retracted", "amended"]


class WallMatch(WireModel):
    """One match: its score and clock as last published, and its partners' items."""

    match_id: MatchId
    home: ClubCode
    away: ClubCode
    state: MatchState
    score: Score
    # None until the match has started.
    clock: MatchClock | None
    # Partner items published (first versions), how many await an editor, corrections issued.
    items: Count
    pending_approvals: Count
    corrections: Count
    # Partners with a graphic on screen at the clock as last published.
    on_air: Annotated[tuple[TenantId, ...], Field(max_length=8, strict=False)]

    @model_validator(mode="after")
    def _consistent(self) -> "WallMatch":
        if self.state == "idle" and (
            self.clock is not None or self.on_air or self.items or self.corrections
        ):
            raise ValueError("a match not started has no clock, items or corrections")
        if self.state != "running" and self.on_air:
            raise ValueError("only a match being played has graphics on air")
        if len(set(self.on_air)) != len(self.on_air):
            raise ValueError("a partner is on air once")
        if self.pending_approvals > self.items:
            raise ValueError("items awaiting an editor are among the items published")
        return self


class WallActivity(WireModel):
    """A partner item as it was published, newest first on the wall."""

    entry_seq: EntrySeq
    match_id: MatchId
    tenant_id: TenantId
    state: ItemState
    # The item's headline as the audience reads it (one line, rendered by code).
    headline: Reason
    clock: MatchClock
    # Written by a model (then verified), rather than filled from a template.
    ai_written: bool


class WallCorrection(WireModel):
    """The latest correction and what the corrections desk did about it."""

    match_id: MatchId
    correction_id: CorrectionId
    summary: Reason
    out_text: Annotated[str, Field(min_length=1, max_length=12)]
    in_text: Annotated[str, Field(min_length=1, max_length=12)]
    # When the corrected event happened, and when the correction arrived, on the match clock.
    event_clock: MatchClock | None
    received_clock: MatchClock
    items_corrected: Count
    partners: Annotated[int, Field(ge=0, le=len(TENANT_LOCALES))]
    languages: Annotated[int, Field(ge=0, le=len(set(TENANT_LOCALES.values())))]
    elapsed_ms: Millis | None


class MatchdayWall(WireModel):
    generated_at: UtcTimestamp
    matches: Annotated[tuple[WallMatch, ...], Field(max_length=MAX_MATCHES, strict=False)]
    activity: Annotated[tuple[WallActivity, ...], Field(max_length=MAX_ACTIVITY, strict=False)]
    latest_correction: WallCorrection | None

    @model_validator(mode="after")
    def _consistent(self) -> "MatchdayWall":
        ids = {m.match_id for m in self.matches}
        if any(a.match_id not in ids for a in self.activity):
            raise ValueError("activity is about the wall's own matches")
        order = [(a.match_id, a.entry_seq) for a in self.activity]
        if any(
            later[0] == earlier[0] and later[1] >= earlier[1]
            for earlier, later in itertools.pairwise(order)
        ):
            # Within a match; across matches the wall orders them by when they were published.
            raise ValueError("activity is listed newest first")
        return self


MATCHDAY_WALL_ADAPTER: TypeAdapter[MatchdayWall] = TypeAdapter(MatchdayWall)


def parse_matchday_wall(raw: object) -> MatchdayWall:
    """Validate decoded wire data (camelCase keys only) into a matchday wall."""
    return MATCHDAY_WALL_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
