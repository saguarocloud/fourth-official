"""Replay a match as if it were live: publish its clock, the moments the detector finds, the
verified insights the Explain stage writes, and corrections when they are issued.

Events are published at their own pace (scaled by `speed`, with long gaps capped), detection runs
incrementally on what has been published, and moments are explained concurrently, so a slow model
never holds up the match.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial

from fourth_official_contracts import (
    AttemptRecord,
    ClockEntry,
    Correction,
    CorrectionEntry,
    EventVoided,
    GoalEvent,
    InsightEntry,
    MatchEvent,
    Moment,
    MomentEntry,
    RenderedInsight,
    Score,
)
from fourth_official_explain import Explanation
from fourth_official_explain.snapshots import ComputedSnapshots
from fourth_official_match_data import MatchRecord
from fourth_official_moments import DetectorState, detect
from fourth_official_replay.log import FeedLog
from fourth_official_stats.prepare import prepare
from fourth_official_verifier import MatchFacts, render_insight

Explainer = Callable[[Moment, MatchFacts], Awaitable[Explanation]]
Sleep = Callable[[float], Awaitable[None]]
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    # How many times faster than real time the match is played.
    speed: float = 8.0
    # Publish the clock at least this often, in match seconds.
    clock_every: int = 60
    # Moments explained at the same time.
    concurrency: int = 3
    # The longest real pause between two events (half-time, VAR), in seconds.
    max_pause: float = 30.0
    # Run detection after this many new events. Detection is incremental and pieces give exactly
    # the whole's moments, so this only delays when a moment is published, never which.
    detect_every: int = 10


def facts_for(record: MatchRecord) -> MatchFacts:
    """What the Verifier may treat as true: the match, its names, snapshots on demand, and voids
    in force from their VAR decisions."""
    return MatchFacts(
        match=record.match,
        club_names=record.club_names,
        player_names={pid: p.name for pid, p in record.players.items()},
        snapshots=ComputedSnapshots(record.match),
        voided=record.void_seqs(),
    )


_VOID_REASONS = {
    "VAR_OFFSIDE": "for offside",
    "VAR_FOUL": "for a foul",
    "VAR_HANDBALL": "for handball",
    "ACCREDITATION_PANEL": "by the accreditation panel",
    "PROVIDER_RESTATEMENT": "by the data provider",
}


def correction_summary(record: MatchRecord, correction: Correction) -> str:
    """What a correction changed, in words, rendered from the match and the squad lists. Never
    fails: an unknown target or reason is described generically."""
    target = next(
        (e for e in record.match.events if e.event_id == correction.target_event_id), None
    )
    club = getattr(target, "team_id", None)
    name = record.club_names.get(club, "") if club else ""
    what = f"{name} goal" if isinstance(target, GoalEvent) and name else "An event"
    when = f" at {target.clock.minute}'" if target is not None else ""
    why = _VOID_REASONS.get(correction.reason, "by a correction")
    if isinstance(correction, EventVoided):
        return f"{what}{when} ruled out {why}"
    new_scorer = correction.changes.scorer_id
    if new_scorer is not None and new_scorer in record.players:
        return f"{what}{when} credited to {record.players[new_scorer].name}"
    return f"{what}{when} amended {why}"


def _correction_entry(
    record: MatchRecord, match_id: str, correction: Correction, entry_seq: int
) -> CorrectionEntry:
    return CorrectionEntry(
        kind="correction",
        entry_seq=entry_seq,
        match_id=match_id,
        correction=correction,
        summary=correction_summary(record, correction),
    )


class _Replay:
    def __init__(
        self, record: MatchRecord, log: FeedLog, explainer: Explainer, config: ReplayConfig
    ) -> None:
        self.record, self.log, self.explainer, self.config = record, log, explainer, config
        self.facts = facts_for(record)
        self.slots = asyncio.Semaphore(config.concurrency)
        self.tasks: set[asyncio.Task[None]] = set()
        self.corrections: list[Correction] = sorted(record.corrections, key=lambda c: c.issued_at)
        self.last_clock = -record.match.seconds(record.match.events[0]) - config.clock_every

    async def clock(self, event: MatchEvent) -> None:
        home, away = self.facts.score_at(event.seq)
        self.last_clock = self.record.match.seconds(event)
        await self.log.publish(
            lambda n: ClockEntry(
                kind="clock",
                entry_seq=n,
                match_id=self.log.match_id,
                as_of_seq=event.seq,
                clock=event.clock,
                score=Score(home=home, away=away),
            )
        )

    async def corrections_due(self, event: MatchEvent | None) -> bool:
        """Publish corrections issued by the time of `event` (all of them, if None)."""
        published = False
        while self.corrections and (
            event is None or self.corrections[0].issued_at <= event.wall_clock
        ):
            correction = self.corrections.pop(0)
            await self.log.publish(
                partial(_correction_entry, self.record, self.log.match_id, correction)
            )
            published = True
        return published

    async def explain(self, moment: Moment) -> None:
        """Explain one moment and publish its insight. Whatever goes wrong is logged and stays
        with this moment: the match and the other moments carry on."""
        try:
            async with self.slots:
                explanation = await self.explainer(moment, self.facts)
            if explanation.insight is None:
                logger.warning("no verified insight for %s", moment.moment_id)
                return
            await self._publish_insight(explanation)
        except Exception:
            logger.exception("explaining %s failed", moment.moment_id)

    async def _publish_insight(self, explanation: Explanation) -> None:
        insight = explanation.insight
        if insight is None:  # pragma: no cover - checked by the caller
            return
        headline, claims = render_insight(insight, self.facts)
        await self.log.publish(
            lambda n: InsightEntry(
                kind="insight",
                entry_seq=n,
                match_id=self.log.match_id,
                insight=insight,
                verdict=explanation.verdict,
                rendered=RenderedInsight(headline=headline, claims=claims),
                attempts=tuple(
                    AttemptRecord(
                        number=a.number,
                        agent=a.agent,
                        model=a.model,
                        outcome=a.outcome,
                        findings=a.findings,  # type: ignore[arg-type]
                        error=a.error,
                    )
                    for a in explanation.attempts
                ),
            )
        )

    async def moment(self, moment: Moment) -> None:
        await self.log.publish(
            lambda n: MomentEntry(
                kind="moment", entry_seq=n, match_id=self.log.match_id, moment=moment
            )
        )
        task = asyncio.create_task(self.explain(moment))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


async def replay(
    record: MatchRecord,
    log: FeedLog,
    explainer: Explainer,
    *,
    config: ReplayConfig | None = None,
    sleep: Sleep = asyncio.sleep,
) -> None:
    """Play the match into `log`, then wait for every explanation and finish the log."""
    config = config or ReplayConfig()
    run = _Replay(record, log, explainer, config)
    events = record.match.events
    state: DetectorState | None = None
    previous: MatchEvent | None = None
    try:
        for index, event in enumerate(events):
            if previous is not None:
                gap = (event.wall_clock - previous.wall_clock).total_seconds() / config.speed
                await sleep(min(max(gap, 0.0), config.max_pause))
            previous = event
            last = index == len(events) - 1
            found: tuple[Moment, ...] = ()
            if last or (index + 1) % config.detect_every == 0 or isinstance(event, GoalEvent):
                state, found = detect(prepare(record.match.context, events[: index + 1]), state)
            corrected = await run.corrections_due(event)
            due = record.match.seconds(event) - run.last_clock >= config.clock_every
            if (
                due
                or corrected
                or found
                or isinstance(event, GoalEvent)
                or index == len(events) - 1
            ):
                await run.clock(event)
            for moment in found:
                await run.moment(moment)
        await run.corrections_due(None)
        await asyncio.gather(*run.tasks)
    finally:
        # However the replay ends (done, failed or cancelled), no explanation outlives it.
        for task in run.tasks:
            task.cancel()
        await asyncio.gather(*run.tasks, return_exceptions=True)
        await log.finish()
