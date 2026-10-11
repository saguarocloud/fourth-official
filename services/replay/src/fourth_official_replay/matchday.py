"""The matchday: the demo's matches, replayed together, one run at a time.

A run spends model tokens, so only one runs at a time, runs start at most once per cooldown
(counted from the start of the last run), and no more than a daily budget of runs start in any
24 hours. When the runs started is kept in a `StartLedger`: the in-memory ledger holds only as long
as the process does, so a deployment that spends real tokens must use a durable one (a replica
that scales to zero forgets its starts). The API runs as a single replica (infra/main.bicep), so
one ledger sees every start.

Each match keeps one feed log for the life of the matchday; a new run resets it, so readers that
opened the feed earlier follow the new run.

An editor's decision on a held item is published as the item's next entry on its match's feed,
while the match runs; after full time the feed is closed and held items stay off air.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from fourth_official_contracts import ClockEntry, TenantItemEntry
from fourth_official_match_data import MatchStore
from fourth_official_replay.log import FeedLog
from fourth_official_replay.partners import Decision, DecisionError, Partners
from fourth_official_replay.replay import Explainer, ReplayConfig, Sleep, replay

MatchState = Literal["idle", "running", "finished", "failed"]
DEFAULT_COOLDOWN_SECONDS = 15 * 60.0
DEFAULT_RUNS_PER_DAY = 24
DAY_SECONDS = 24 * 60 * 60.0


class StartLedger(Protocol):
    """When matchday runs started (epoch seconds), kept wherever the spend guards need it."""

    async def recent(self, since: float) -> tuple[float, ...]: ...

    async def claim(self, started: float, check: Callable[[tuple[float, ...]], None]) -> None:
        """Record `started` if `check` accepts the starts held at that moment (it raises if
        not). Atomic: no start recorded elsewhere can slip between the check and the record."""
        ...


class InMemoryLedger:
    """Starts kept in the process: enough for tests and template-only runs, which cost nothing."""

    def __init__(self) -> None:
        self._starts: tuple[float, ...] = ()

    async def recent(self, since: float) -> tuple[float, ...]:
        return tuple(t for t in self._starts if t >= since)

    async def claim(self, started: float, check: Callable[[tuple[float, ...]], None]) -> None:
        check(self._starts)
        self._starts = (*self._starts[-(DEFAULT_RUNS_PER_DAY * 2) :], started)


class UnknownItemError(LookupError):
    """No such match, or no such item of the partner on its feed this run."""


class MatchdayBusyError(RuntimeError):
    """A run is under way, or one may not start yet. The message is safe to show."""


@dataclass(frozen=True, slots=True)
class Availability:
    """Whether a run may start now; if not, why (safe to show) and, when known, from when."""

    ready: bool
    blocked_by: Literal["running", "cooldown", "daily_limit"] | None = None
    reason: str | None = None
    # Epoch seconds from which a run may start; None while a run is under way.
    ready_at: float | None = None


@dataclass(frozen=True, slots=True)
class MatchStatus:
    match_id: str
    state: MatchState
    entries: int


class Matchday:
    def __init__(  # noqa: PLR0913 - the matchday's configuration, keyword-only after the store
        self,
        store: MatchStore,
        explainer: Explainer,
        *,
        config: ReplayConfig | None = None,
        cooldown: float = DEFAULT_COOLDOWN_SECONDS,
        runs_per_day: int = DEFAULT_RUNS_PER_DAY,
        ledger: StartLedger | None = None,
        sleep: Sleep = asyncio.sleep,
        partners: Callable[[], Partners] | None = None,
    ) -> None:
        self._store, self._explainer, self._sleep = store, explainer, sleep
        # Each match of each run gets its own partners' state (their director schedules).
        self._partners = partners
        self._config = config or ReplayConfig()
        self._cooldown, self._runs_per_day = cooldown, runs_per_day
        self._feeds = {match_id: FeedLog(match_id) for match_id in store.match_ids()}
        self._runs: dict[str, asyncio.Task[None]] = {}
        # This run's partners for each match: their schedules place an approved item on air.
        self._run_partners: dict[str, Partners] = {}
        # One decision at a time, so two editors cannot both decide the same item.
        self._deciding = asyncio.Lock()
        self._ledger = ledger or InMemoryLedger()
        self._lock = asyncio.Lock()

    def feed(self, match_id: str) -> FeedLog:
        return self._feeds[match_id]

    def status(self) -> tuple[MatchStatus, ...]:
        return tuple(
            MatchStatus(match_id, self._state(match_id), len(feed.entries))
            for match_id, feed in self._feeds.items()
        )

    def _state(self, match_id: str) -> MatchState:
        run = self._runs.get(match_id)
        if run is None:
            return "idle"
        if not run.done():
            return "running"
        return "failed" if run.cancelled() or run.exception() else "finished"

    @property
    def runs_per_day(self) -> int:
        return self._runs_per_day

    @property
    def running(self) -> bool:
        return any(not run.done() for run in self._runs.values())

    def _judge(self, starts: tuple[float, ...], moment: float) -> Availability:
        """The guards over the starts recorded so far, ignoring a run under way."""
        # A start counts against the day for a full 24 hours, and no longer.
        today = sorted(t for t in starts if t > moment - DAY_SECONDS)
        cooled = today[-1] + self._cooldown if today else moment
        if len(today) >= self._runs_per_day:
            return Availability(
                ready=False,
                blocked_by="daily_limit",
                reason="the matchday has been replayed as often as allowed today",
                ready_at=max(cooled, today[-self._runs_per_day] + DAY_SECONDS),
            )
        if moment < cooled:
            return Availability(
                ready=False,
                blocked_by="cooldown",
                reason=f"the matchday can be replayed again in {int(cooled - moment)} seconds",
                ready_at=cooled,
            )
        return Availability(ready=True)

    async def availability(self, *, now: float | None = None) -> Availability:
        """Whether `start` would accept a run now, without starting one."""
        moment = time.time() if now is None else now
        if self.running:
            return Availability(
                ready=False, blocked_by="running", reason="a matchday is already running"
            )
        return self._judge(await self._ledger.recent(moment - DAY_SECONDS), moment)

    def _refuse_unless_ready(self, starts: tuple[float, ...], moment: float) -> None:
        available = self._judge(starts, moment)
        if not available.ready:
            raise MatchdayBusyError(available.reason)

    async def start(self, *, now: float | None = None) -> None:
        """Replay every match from the start. Refuses while a run is under way, during the
        cooldown, and beyond the daily budget."""
        moment = time.time() if now is None else now
        async with self._lock:
            if self.running:
                raise MatchdayBusyError("a matchday is already running")
            await self._ledger.claim(
                moment, lambda starts: self._refuse_unless_ready(starts, moment)
            )
            records = {match_id: self._store.record(match_id) for match_id in self._feeds}
            for feed in self._feeds.values():
                await feed.reset()
            self._run_partners = (
                {match_id: self._partners() for match_id in records} if self._partners else {}
            )
            self._runs = {
                match_id: asyncio.create_task(
                    replay(
                        record,
                        self._feeds[match_id],
                        self._explainer,
                        config=self._config,
                        sleep=self._sleep,
                        partners=self._run_partners.get(match_id),
                    ),
                    name=f"replay-{match_id}",
                )
                for match_id, record in records.items()
            }

    async def decide(
        self,
        match_id: str,
        tenant_id: str,
        item_id: str,
        decision: Decision,
        *,
        reason: str | None,
        now: datetime,
    ) -> TenantItemEntry:
        """Publish the duty editor's decision on a held item as its next entry. Raises
        `UnknownItemError` for an item not on the feed, `DecisionError` (safe to show) for one
        that cannot be decided now."""
        feed = self._feeds.get(match_id)
        if feed is None:
            raise UnknownItemError("unknown match")
        async with self._deciding:
            entries = feed.entries
            item = next(
                (
                    e
                    for e in reversed(entries)
                    if isinstance(e, TenantItemEntry)
                    and e.tenant_id == tenant_id
                    and e.overlay.item_id == item_id
                ),
                None,
            )
            if item is None:
                raise UnknownItemError("no such item on this match's feed")
            partners = self._run_partners.get(match_id)
            if feed.finished or partners is None:
                raise DecisionError("the match has reached full time; held items stay off air")
            clocks = [e.clock for e in entries if isinstance(e, ClockEntry)]
            at = clocks[-1] if clocks else item.overlay.in_at
            build = await partners.decide(item, decision, reason=reason, at=at, now=now)
            try:
                entry = await feed.publish(build)
            except RuntimeError:
                raise DecisionError(
                    "the match has reached full time; held items stay off air"
                ) from None
        if not isinstance(entry, TenantItemEntry):  # pragma: no cover - built as a tenant item
            raise TypeError("a decision is published as the partner's item")
        return entry

    async def wait(self) -> None:
        """Wait for the current run to end, however it ends."""
        await asyncio.gather(*self._runs.values(), return_exceptions=True)

    async def stop(self) -> None:
        """Cancel a run under way (on shutdown) and wait for it to wind down."""
        for run in self._runs.values():
            run.cancel()
        await self.wait()
