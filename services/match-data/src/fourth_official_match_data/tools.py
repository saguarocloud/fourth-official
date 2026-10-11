"""The Match Data tools: read-only facts about a match, as wire-format dictionaries.

Every tool is bounded by what has been published: `as_of_seq` defaults to the live position and
can never reach past it. Numbers come from the stats engine; nothing here is estimated.
"""

from typing import Any

from fourth_official_contracts import GoalEvent, MetricName, MetricWindow
from fourth_official_match_data.store import MatchDataError, MatchRecord, MatchStore
from fourth_official_stats.snapshots import SnapshotKey, snapshot

MAX_EVENTS = 100
COMPARE_LAG_SECONDS = 5 * 60
Wire = dict[str, Any]


def _clubs(record: MatchRecord) -> tuple[str, str]:
    return record.match.context.home, record.match.context.away


def list_matches(store: MatchStore) -> list[Wire]:
    listed = []
    for match_id in store.match_ids():
        record = store.record(match_id)
        home, away = _clubs(record)
        live = record.resolve(None)
        listed.append(
            {
                "matchId": match_id,
                "home": home,
                "away": away,
                "homeName": record.club_names[home],
                "awayName": record.club_names[away],
                "liveSeq": live.seq,
                "clock": live.clock.to_wire(),
            }
        )
    return listed


def get_match_state(store: MatchStore, match_id: str, *, as_of_seq: int | None = None) -> Wire:
    record = store.record(match_id)
    moment = record.resolve(as_of_seq)
    voided = record.voided_at(moment)
    home, away = _clubs(record)
    goals = [
        e
        for e in record.match.events
        if isinstance(e, GoalEvent) and e.seq <= moment.seq and e.event_id not in voided
    ]
    return {
        "matchId": match_id,
        "asOfSeq": moment.seq,
        "clock": moment.clock.to_wire(),
        "home": home,
        "away": away,
        "score": {
            "home": sum(g.team_id == home for g in goals),
            "away": sum(g.team_id == away for g in goals),
        },
        "voidedEventIds": sorted(voided),
    }


def _check_scope(record: MatchRecord, scope: str) -> None:
    if scope != "match" and scope not in _clubs(record):
        raise MatchDataError(f"{scope} is not playing in {record.match.context.match_id}")


def get_metric(
    store: MatchStore,
    match_id: str,
    *,
    metric: MetricName,
    scope: str,
    window: MetricWindow,
    as_of_seq: int | None = None,
) -> Wire:
    record = store.record(match_id)
    _check_scope(record, scope)
    moment = record.resolve(as_of_seq)
    try:
        frozen = snapshot(
            record.match, as_of_seq=moment.seq, key=SnapshotKey(metric, scope, window)
        )
    except ValueError as refused:
        raise MatchDataError(str(refused)) from None
    return frozen.to_wire()


def compare_windows(
    store: MatchStore,
    match_id: str,
    *,
    metric: MetricName,
    scope: str,
    as_of_seq: int | None = None,
) -> Wire:
    """The last five minutes against the fifteen before them: the comparison behind shifts."""
    record = store.record(match_id)
    now = record.resolve(as_of_seq)
    lag = record.match.seconds(now) - COMPARE_LAG_SECONDS
    earlier = [
        e for e in record.match.events if e.seq <= now.seq and record.match.seconds(e) <= lag
    ]
    if not earlier:
        raise MatchDataError("too early in the match to compare windows")
    return {
        "current": get_metric(
            store, match_id, metric=metric, scope=scope, window="5m", as_of_seq=now.seq
        ),
        "baseline": get_metric(
            store, match_id, metric=metric, scope=scope, window="15m", as_of_seq=earlier[-1].seq
        ),
    }


def get_events(
    store: MatchStore,
    match_id: str,
    *,
    from_seq: int,
    to_seq: int,
    types: list[str] | None = None,
) -> list[Wire]:
    """Published events in a seq range, in order, at most `MAX_EVENTS` of them."""
    record = store.record(match_id)
    if from_seq < 1 or to_seq < from_seq:
        raise MatchDataError("from_seq must be at least 1 and no later than to_seq")
    limit = min(to_seq, record.live_seq)
    wanted = set(types) if types else None
    events = [
        e
        for e in record.match.events
        if from_seq <= e.seq <= limit and (wanted is None or e.type in wanted)
    ]
    return [e.to_wire() for e in events[:MAX_EVENTS]]


def get_player(store: MatchStore, match_id: str, *, player_id: str) -> Wire:
    record = store.record(match_id)
    player = record.players.get(player_id)
    if player is None:
        raise MatchDataError(f"player {player_id[:8]} is not in {match_id}")
    return {
        "playerId": player.player_id,
        "name": player.name,
        "club": player.player_id[:3],
        "shirt": player.shirt,
        "position": player.position.name.lower(),
    }


def list_moments(store: MatchStore, match_id: str, *, as_of_seq: int | None = None) -> list[Wire]:
    record = store.record(match_id)
    moment = record.resolve(as_of_seq)
    return [m.to_wire() for m in record.moments if m.as_of_seq <= moment.seq]
