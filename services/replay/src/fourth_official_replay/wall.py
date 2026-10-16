"""The Control Room's wall, computed by code from each match's feed: the score and clock as last
published, which partners have a graphic on screen, what awaits an editor, corrections, the
latest partner items (newest first across matches, by when they were published) and the latest
correction with what the corrections desk did about it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from fourth_official_contracts import (
    ClockEntry,
    CorrectionEntry,
    CorrectionReportEntry,
    FeedEntry,
    MatchClock,
    MatchdayWall,
    Score,
    TenantId,
    TenantItemEntry,
    WallActivity,
    WallCorrection,
    WallMatch,
)
from fourth_official_contracts.operations import MatchState
from fourth_official_match_data import MatchRecord
from fourth_official_replay.log import FeedLog, RunTiming

ACTIVITY = 12


@dataclass(frozen=True, slots=True)
class Played:
    """One match as the wall needs it: its clubs, its state, its feed and the feed's timing."""

    match_id: str
    home: str
    away: str
    state: MatchState
    entries: tuple[FeedEntry, ...]
    timing: RunTiming
    # When each event happened, on the match clock (to place a corrected event).
    event_clocks: Mapping[str, MatchClock]


def played_from(record: MatchRecord, state: MatchState, log: FeedLog) -> Played:
    entries, timing = log.snapshot()
    context = record.match.context
    return Played(
        match_id=log.match_id,
        home=context.home,
        away=context.away,
        state=state,
        entries=entries,
        timing=timing,
        event_clocks={e.event_id: e.clock for e in record.match.events},
    )


def _latest_items(entries: Sequence[FeedEntry]) -> dict[str, TenantItemEntry]:
    """Each partner item as it stands now (a decision or a correction republishes it)."""
    latest: dict[str, TenantItemEntry] = {}
    for e in entries:
        if isinstance(e, TenantItemEntry):
            latest[e.overlay.item_id] = e
    return latest


def _covers(item: TenantItemEntry, clock: MatchClock) -> bool:
    start, end = item.overlay.in_at, item.overlay.out_at
    now = (clock.minute, clock.second)
    return start.period == clock.period and (start.minute, start.second) <= now < (
        end.minute,
        end.second,
    )


def _match(played: Played) -> WallMatch:
    clocks = [e for e in played.entries if isinstance(e, ClockEntry)]
    last = clocks[-1] if clocks else None
    latest = _latest_items(played.entries)
    narrative = [e for e in latest.values() if e.localized is not None]
    on_air: list[TenantId] = []
    if last is not None:
        for item in latest.values():
            covering = item.state == "on_air" and item.item_kind != "score"
            if covering and _covers(item, last.clock) and item.tenant_id not in on_air:
                on_air.append(item.tenant_id)
    return WallMatch(
        match_id=played.match_id,
        home=played.home,
        away=played.away,
        state=played.state,
        score=last.score if last else Score(home=0, away=0),
        clock=last.clock if last else None,
        items=sum(1 for e in narrative if e.localized is not None and e.localized.version == 1),
        pending_approvals=sum(e.state == "pending_approval" for e in narrative),
        corrections=sum(isinstance(e, CorrectionEntry) for e in played.entries),
        on_air=tuple(sorted(on_air)),
    )


def _activity(played: Played) -> list[tuple[float, WallActivity]]:
    stamps = dict(zip((e.entry_seq for e in played.entries), played.timing.published, strict=True))
    found = []
    for e in played.entries:
        if isinstance(e, TenantItemEntry) and e.rendered is not None and e.localized is not None:
            found.append(
                (
                    stamps[e.entry_seq],
                    WallActivity(
                        entry_seq=e.entry_seq,
                        match_id=e.match_id,
                        tenant_id=e.tenant_id,
                        state=e.state,
                        headline=e.rendered.headline,
                        clock=e.overlay.in_at,
                        # Who wrote the words the audience reads: a model, or a template.
                        ai_written=e.localized.provenance.produced_by == "model",
                    ),
                )
            )
    return found


def _corrections(played: Played) -> list[tuple[float, WallCorrection]]:
    stamps = dict(zip((e.entry_seq for e in played.entries), played.timing.published, strict=True))
    # A correction is reported when it is issued, and again for each insight published after it
    # that rests on it: what the desk did is every report's actions, timed by the first.
    reports: dict[str, list[CorrectionReportEntry]] = {}
    for e in played.entries:
        if isinstance(e, CorrectionReportEntry):
            reports.setdefault(e.correction_id, []).append(e)
    clock: MatchClock | None = None
    found = []
    for e in played.entries:
        if isinstance(e, ClockEntry):
            clock = e.clock
        if not isinstance(e, CorrectionEntry) or clock is None:
            continue
        cid = e.correction.correction_id
        reported = reports.get(cid, [])
        actions = [a for r in reported for a in r.actions]
        found.append(
            (
                stamps[e.entry_seq],
                WallCorrection(
                    match_id=e.match_id,
                    correction_id=cid,
                    summary=e.summary,
                    out_text=e.out_text,
                    in_text=e.in_text,
                    event_clock=played.event_clocks.get(e.correction.target_event_id),
                    received_clock=clock,
                    items_corrected=len(actions),
                    partners=len({a.tenant_id for a in actions}),
                    languages=len({a.locale for a in actions}),
                    elapsed_ms=reported[0].elapsed_ms if reported else None,
                ),
            )
        )
    return found


def wall(
    played: Sequence[Played], *, generated_at: datetime, activity_limit: int = ACTIVITY
) -> MatchdayWall:
    """The whole matchday's wall: every match, the latest items and the latest correction."""
    activity = sorted(
        (found for p in played for found in _activity(p)), key=lambda f: f[0], reverse=True
    )
    corrections = sorted((found for p in played for found in _corrections(p)), key=lambda f: f[0])
    return MatchdayWall(
        generated_at=generated_at,
        matches=tuple(_match(p) for p in played),
        activity=tuple(a for _, a in activity[:activity_limit]),
        latest_correction=corrections[-1][1] if corrections else None,
    )
