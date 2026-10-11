"""The matchday: the demo's matches, replayed together, one run at a time.

A run spends model tokens, so only one runs at a time, runs start at most once per cooldown
(counted from the start of the last run), and no more than a daily budget of runs start in any
24 hours. When the runs started is kept in a `StartLedger`: the in-memory ledger holds only as long
as the process does, so a deployment that spends real tokens must use a durable one (a replica
that scales to zero forgets its starts). The API runs as a single replica (infra/main.bicep), so
one ledger sees every start.

Each match keeps one feed log for the life of the matchday; a new run resets it, so readers that
opened the feed earlier follow the new run.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Literal, Protocol

from fourth_official_match_data import MatchStore
from fourth_official_replay.log import FeedLog
from fourth_official_replay.replay import Explainer, ReplayConfig, Sleep, replay

MatchState = Literal["idle", "running", "finished", "failed"]
DEFAULT_COOLDOWN_SECONDS = 15 * 60.0
DEFAULT_RUNS_PER_DAY = 24
DAY_SECONDS = 24 * 60 * 60.0


class StartLedger(Protocol):
    """When matchday runs started (epoch seconds), kept wherever the spend guards need it."""

    async def recent(self, since: float) -> tuple[float, ...]: ...

    async def record(self, started: float) -> None: ...


class InMemoryLedger:
    """Starts kept in the process: enough for tests and template-only runs, which cost nothing."""

    def __init__(self) -> None:
        self._starts: tuple[float, ...] = ()

    async def recent(self, since: float) -> tuple[float, ...]:
        return tuple(t for t in self._starts if t >= since)

    async def record(self, started: float) -> None:
        self._starts = (*self._starts[-(DEFAULT_RUNS_PER_DAY * 2) :], started)


class MatchdayBusyError(RuntimeError):
    """A run is under way, or one may not start yet. The message is safe to show."""


@dataclass(frozen=True, slots=True)
class MatchStatus:
    match_id: str
    state: MatchState
    entries: int


class Matchday:
    def __init__(
        self,
        store: MatchStore,
        explainer: Explainer,
        *,
        config: ReplayConfig | None = None,
        cooldown: float = DEFAULT_COOLDOWN_SECONDS,
        runs_per_day: int = DEFAULT_RUNS_PER_DAY,
        ledger: StartLedger | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._store, self._explainer, self._sleep = store, explainer, sleep
        self._config = config or ReplayConfig()
        self._cooldown, self._runs_per_day = cooldown, runs_per_day
        self._feeds = {match_id: FeedLog(match_id) for match_id in store.match_ids()}
        self._runs: dict[str, asyncio.Task[None]] = {}
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
    def running(self) -> bool:
        return any(not run.done() for run in self._runs.values())

    async def _check_can_start(self, now: float) -> None:
        if self.running:
            raise MatchdayBusyError("a matchday is already running")
        today = await self._ledger.recent(now - DAY_SECONDS)
        if today and now - max(today) < self._cooldown:
            wait = int(self._cooldown - (now - max(today)))
            raise MatchdayBusyError(f"the matchday can be replayed again in {wait} seconds")
        if len(today) >= self._runs_per_day:
            raise MatchdayBusyError("the matchday has been replayed as often as allowed today")

    async def start(self, *, now: float | None = None) -> None:
        """Replay every match from the start. Refuses while a run is under way, during the
        cooldown, and beyond the daily budget."""
        moment = time.time() if now is None else now
        async with self._lock:
            await self._check_can_start(moment)
            await self._ledger.record(moment)
            records = {match_id: self._store.record(match_id) for match_id in self._feeds}
            for feed in self._feeds.values():
                await feed.reset()
            self._runs = {
                match_id: asyncio.create_task(
                    replay(
                        record,
                        self._feeds[match_id],
                        self._explainer,
                        config=self._config,
                        sleep=self._sleep,
                    ),
                    name=f"replay-{match_id}",
                )
                for match_id, record in records.items()
            }

    async def wait(self) -> None:
        """Wait for the current run to end, however it ends."""
        await asyncio.gather(*self._runs.values(), return_exceptions=True)

    async def stop(self) -> None:
        """Cancel a run under way (on shutdown) and wait for it to wind down."""
        for run in self._runs.values():
            run.cancel()
        await self.wait()
