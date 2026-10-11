"""What the Match Data tools return: typed wire models, so every tool publishes an output schema."""

from typing import Annotated, Literal

from pydantic import Field

from fourth_official_contracts import (
    ClubCode,
    EventId,
    MatchClock,
    MatchEvent,
    MatchId,
    MetricSnapshot,
    Moment,
    PlayerId,
    Score,
    WireModel,
)

Seq = Annotated[int, Field(ge=0)]


class MatchSummary(WireModel):
    match_id: MatchId
    home: ClubCode
    away: ClubCode
    home_name: str
    away_name: str
    # 0 and no clock until the first event is published.
    live_seq: Seq
    clock: MatchClock | None


class MatchList(WireModel):
    matches: tuple[MatchSummary, ...]


class MatchState(WireModel):
    match_id: MatchId
    as_of_seq: Seq
    clock: MatchClock
    home: ClubCode
    away: ClubCode
    # Without goals voided by corrections in force at that moment.
    score: Score
    voided_event_ids: tuple[EventId, ...]


class WindowComparison(WireModel):
    current: MetricSnapshot
    baseline: MetricSnapshot


class EventPage(WireModel):
    events: tuple[MatchEvent, ...]
    # Where to continue if the range held more events than one page; None when complete.
    next_seq: Seq | None


class PlayerInfo(WireModel):
    player_id: PlayerId
    name: str
    club: ClubCode
    shirt: Annotated[int, Field(ge=1, le=99)]
    position: Literal["goalkeeper", "defender", "midfielder", "forward"]


class MomentList(WireModel):
    moments: tuple[Moment, ...]
