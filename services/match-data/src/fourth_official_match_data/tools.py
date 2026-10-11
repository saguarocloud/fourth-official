"""The Match Data tools: read-only facts about a match, as typed wire models.

Every tool is bounded by what has been published: `as_of_seq` defaults to the live position and
can never reach past it. Numbers come from the stats engine; nothing here is estimated. Refusals
are fixed messages that never repeat the caller's input.
"""

from fourth_official_contracts import (
    GoalEvent,
    MetricName,
    MetricSnapshot,
    MetricWindow,
    Score,
    club_of,
)
from fourth_official_match_data.models import (
    EventPage,
    MatchList,
    MatchState,
    MatchSummary,
    MomentList,
    PlayerInfo,
    WindowComparison,
)
from fourth_official_match_data.store import MatchDataError, MatchRecord, MatchStore
from fourth_official_stats.snapshots import SnapshotKey, snapshot

MAX_EVENTS = 100
COMPARE_LAG_SECONDS = 5 * 60
_POSITIONS = {"GK": "goalkeeper", "DF": "defender", "MF": "midfielder", "FW": "forward"}


def _clubs(record: MatchRecord) -> tuple[str, str]:
    return record.match.context.home, record.match.context.away


def list_matches(store: MatchStore) -> MatchList:
    summaries = []
    for match_id in store.match_ids():
        record = store.record(match_id)
        home, away = _clubs(record)
        started = record.live_seq > 0
        summaries.append(
            MatchSummary(
                match_id=match_id,
                home=home,
                away=away,
                home_name=record.club_names[home],
                away_name=record.club_names[away],
                live_seq=record.live_seq,
                clock=record.resolve(None).clock if started else None,
            )
        )
    return MatchList(matches=tuple(summaries))


def get_match_state(
    store: MatchStore, match_id: str, *, as_of_seq: int | None = None
) -> MatchState:
    record = store.record(match_id)
    moment = record.resolve(as_of_seq)
    voided = record.voided_at(moment)
    home, away = _clubs(record)
    goals = [
        e
        for e in record.match.events
        if isinstance(e, GoalEvent) and e.seq <= moment.seq and e.event_id not in voided
    ]
    return MatchState(
        match_id=match_id,
        as_of_seq=moment.seq,
        clock=moment.clock,
        home=home,
        away=away,
        score=Score(
            home=sum(g.team_id == home for g in goals), away=sum(g.team_id == away for g in goals)
        ),
        voided_event_ids=tuple(sorted(voided)),
    )


def _check_scope(record: MatchRecord, scope: str) -> None:
    if scope != "match" and scope not in _clubs(record):
        raise MatchDataError("that club is not playing in this match")


def get_metric(
    store: MatchStore,
    match_id: str,
    *,
    metric: MetricName,
    scope: str,
    window: MetricWindow,
    as_of_seq: int | None = None,
) -> MetricSnapshot:
    record = store.record(match_id)
    _check_scope(record, scope)
    moment = record.resolve(as_of_seq)
    try:
        return snapshot(record.match, as_of_seq=moment.seq, key=SnapshotKey(metric, scope, window))
    except ValueError:
        raise MatchDataError("that metric is not measured for that scope") from None


def compare_windows(
    store: MatchStore,
    match_id: str,
    *,
    metric: MetricName,
    scope: str,
    as_of_seq: int | None = None,
) -> WindowComparison:
    """The last five minutes against the fifteen before them: the comparison behind shifts."""
    record = store.record(match_id)
    now = record.resolve(as_of_seq)
    lag = record.match.seconds(now) - COMPARE_LAG_SECONDS
    earlier = [
        e for e in record.match.events if e.seq <= now.seq and record.match.seconds(e) <= lag
    ]
    if not earlier:
        raise MatchDataError("too early in the match to compare windows")
    return WindowComparison(
        current=get_metric(
            store, match_id, metric=metric, scope=scope, window="5m", as_of_seq=now.seq
        ),
        baseline=get_metric(
            store, match_id, metric=metric, scope=scope, window="15m", as_of_seq=earlier[-1].seq
        ),
    )


def get_events(
    store: MatchStore,
    match_id: str,
    *,
    from_seq: int,
    to_seq: int,
    types: list[str] | None = None,
) -> EventPage:
    """Published events in a seq range, in order: a page of at most `MAX_EVENTS`, with where to
    continue if there are more."""
    record = store.record(match_id)
    if from_seq < 1 or to_seq < from_seq:
        raise MatchDataError("from_seq must be at least 1 and no later than to_seq")
    if from_seq > record.live_seq:
        raise MatchDataError("that point of the match has not been published yet")
    limit = min(to_seq, record.live_seq)
    wanted = set(types) if types else None
    events = [
        e
        for e in record.match.events
        if from_seq <= e.seq <= limit and (wanted is None or e.type in wanted)
    ]
    page = events[:MAX_EVENTS]
    more = len(events) > MAX_EVENTS
    return EventPage(events=tuple(page), next_seq=events[MAX_EVENTS].seq if more else None)


def get_player(store: MatchStore, match_id: str, *, player_id: str) -> PlayerInfo:
    record = store.record(match_id)
    player = record.players.get(player_id)
    if player is None:
        raise MatchDataError("that player is not in this match")
    return PlayerInfo(
        player_id=player.player_id,
        name=player.name,
        club=club_of(player.player_id),
        shirt=player.shirt,
        position=_POSITIONS[player.position.value],  # type: ignore[arg-type]
    )


def list_moments(store: MatchStore, match_id: str, *, as_of_seq: int | None = None) -> MomentList:
    record = store.record(match_id)
    moment = record.resolve(as_of_seq)
    return MomentList(moments=tuple(m for m in record.moments if m.as_of_seq <= moment.seq))
