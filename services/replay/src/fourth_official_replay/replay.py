"""Replay a match as if it were live: publish its clock, the moments the detector finds, the
verified insights the Explain stage writes, and corrections when they are issued.

Events are published at their own pace (scaled by `speed`, with long gaps capped), detection runs
incrementally on what has been published, and moments are explained concurrently, so a slow model
never holds up the match.
"""

import asyncio
import contextlib
import itertools
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial

from fourth_official_contracts import (
    AttemptRecord,
    ClockEntry,
    Correction,
    CorrectionEntry,
    EventVoided,
    GoalEvent,
    InsightEntry,
    MatchClock,
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
from fourth_official_replay.corrections import corrected_facts, report_entry, touched
from fourth_official_replay.log import FeedLog
from fourth_official_replay.partners import EntryBuilder, Partners
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


def _board_player(record: MatchRecord, player_id: str | None) -> str:
    player = record.players.get(player_id or "")
    return f"{player.player_id[:3]} {player.shirt:02d}" if player else "?"


def correction_board(record: MatchRecord, correction: Correction) -> tuple[str, str]:
    """What went out and what came in, for the OUT/IN board."""
    target = next(
        (e for e in record.match.events if e.event_id == correction.target_event_id), None
    )
    if isinstance(correction, EventVoided):
        if target is None:
            return "EVENT", "VOID"
        facts = facts_for(record)
        decided = record.void_seqs().get(correction.target_event_id, target.seq)
        home, away = facts.score_at(decided - 1)
        after_home, after_away = facts.score_at(decided)
        return f"{home}-{away}", f"{after_home}-{after_away}"
    scorer = getattr(target, "scorer_id", None)
    new_scorer = correction.changes.scorer_id
    if new_scorer is not None:
        return _board_player(record, scorer), _board_player(record, new_scorer)
    return "AS PUBLISHED", "AMENDED"


def _correction_entry(
    record: MatchRecord, match_id: str, correction: Correction, entry_seq: int
) -> CorrectionEntry:
    out_text, in_text = correction_board(record, correction)
    return CorrectionEntry(
        kind="correction",
        entry_seq=entry_seq,
        match_id=match_id,
        correction=correction,
        summary=correction_summary(record, correction),
        out_text=out_text,
        in_text=in_text,
    )


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Clocks:
    """When the corrections desk starts (wall time) and how long it takes (seconds)."""

    wall: Callable[[], datetime] = _now
    elapsed: Callable[[], float] = time.monotonic


def fixed_clocks() -> Clocks:
    """Clocks for a reproducible replay (the recorded fixtures): the desk always starts at the
    same moment, and each of its readings is 4 ms after the last."""
    ticks = itertools.count()
    return Clocks(
        wall=lambda: datetime(2026, 10, 11, 15, 0, tzinfo=UTC),
        elapsed=lambda: next(ticks) * 0.004,
    )


class _Replay:
    def __init__(
        self,
        record: MatchRecord,
        log: FeedLog,
        explainer: Explainer,
        *,
        config: ReplayConfig,
        partners: Partners | None,
        clocks: Clocks,
    ) -> None:
        self.record, self.log, self.explainer, self.config = record, log, explainer, config
        self.clocks = clocks
        self.partners = partners
        # Where the match is as last published, and the score the partners last showed.
        self.now: MatchClock = record.match.events[0].clock
        self.shown: tuple[int, int] | None = None
        self.facts = facts_for(record)
        self.slots = asyncio.Semaphore(config.concurrency)
        self.tasks: set[asyncio.Task[None]] = set()
        self.corrections: list[Correction] = sorted(record.corrections, key=lambda c: c.issued_at)
        # Corrections issued so far, the facts with their amendments, and, per correction, the
        # partner items the desk has dealt with and the versions it made: each correction acts on
        # an item once, however the work arrives, and a later correction still reaches them.
        self.issued: list[Correction] = []
        self.corrected = self.facts
        self.handled: set[tuple[str, str]] = set()
        self.desk_lock = asyncio.Lock()
        self.last_clock = -record.match.seconds(record.match.events[0]) - config.clock_every

    async def clock(self, event: MatchEvent) -> None:
        home, away = self.facts.score_at(event.seq)
        self.last_clock = self.record.match.seconds(event)
        self.now = event.clock
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
        if self.partners is not None and self.shown != (home, away):
            self.shown = (home, away)
            context = self.record.match.context
            await self._publish_all(
                await self.partners.score(
                    match_id=self.log.match_id,
                    as_of_seq=event.seq,
                    home=context.home,
                    away=context.away,
                    score=(home, away),
                    at=event.clock,
                )
            )

    async def _publish_all(self, builders: list[EntryBuilder]) -> None:
        for build in builders:
            await self.log.publish(build)

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
            self.issued.append(correction)
            self.corrected = corrected_facts(self.corrected, correction)
            if self.partners is not None:
                await self._publish_all(
                    await self.partners.correction(correction, self.facts, self.now)
                )
                try:
                    await self.desk(correction)
                except Exception:
                    # The match carries on; what the desk did not reach stays as it was, logged.
                    logger.exception("the corrections desk failed on %s", correction.correction_id)
            published = True
        return published

    async def desk(self, correction: Correction, only: frozenset[str] | None = None) -> None:
        """Apply a correction to the partners' items resting on it, each item once, and report
        what was done and how long it took. On issue, the report is published even
        when nothing was touched; for a late insight, only when something was."""
        if self.partners is None:  # pragma: no cover - called with partners only
            return
        async with self.desk_lock:
            started, began = self.clocks.wall(), self.clocks.elapsed()
            entries = self.log.entries
            found, _ = touched(entries, correction, only=only)
            cid = correction.correction_id
            done = frozenset(item for c, item in self.handled if c == cid)
            builders, actions = await self.partners.correct(
                correction, entries, self.corrected, self.now, only=only, skip=done
            )
            await self._publish_all(builders)
            # Marked once published, so work that failed part way is not taken as done.
            self.handled |= {(cid, a.item_id) for a in actions}
            self.handled |= {(cid, a.new_item_id) for a in actions if a.new_item_id is not None}
            if only is not None and not actions:
                return
            elapsed = int((self.clocks.elapsed() - began) * 1000)
            await self.log.publish(
                report_entry(correction, found, actions, started_at=started, elapsed_ms=elapsed)
            )

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
            if self.partners is not None:
                # Each partner's item goes out the moment it is ready.
                items = self.partners.insight(explanation.insight, moment, self.facts, self.now)
                # Closed however the loop ends, so no partner's work outlives a failed publish.
                async with contextlib.aclosing(items) as ready:
                    async for build in ready:
                        await self.log.publish(build)
                # Published after a correction it rests on: the desk deals with it now.
                for correction in list(self.issued):
                    await self.desk(correction, frozenset({explanation.insight.insight_id}))
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
                        input_tokens=a.input_tokens,
                        output_tokens=a.output_tokens,
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
    partners: Partners | None = None,
    clocks: Clocks | None = None,
) -> None:
    """Play the match into `log`, then wait for every explanation and finish the log. With
    `partners`, each partner's items are published too. `clocks` time the corrections desk
    (fixed ones make a replay reproducible, as the recorded fixtures need)."""
    config = config or ReplayConfig()
    run = _Replay(
        record, log, explainer, config=config, partners=partners, clocks=clocks or Clocks()
    )
    events = record.match.events
    state: DetectorState | None = None
    previous: MatchEvent | None = None
    try:
        for index, event in enumerate(events):
            if previous is not None:
                gap = (event.wall_clock - previous.wall_clock).total_seconds() / config.speed
                await sleep(min(max(gap, 0.0), config.max_pause))
            previous = event
            log.played(event.seq)
            last = index == len(events) - 1
            found: tuple[Moment, ...] = ()
            if last or (index + 1) % config.detect_every == 0 or isinstance(event, GoalEvent):
                state, found = detect(prepare(record.match.context, events[: index + 1]), state)
            # Corrections issued by now are timed at this event, not the last published clock.
            run.now = event.clock
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
