"""The matchday: the demo's matches, replayed together, one run at a time.

A run spends model tokens, so only one runs at a time, runs start at most once per cooldown
(counted from the start of the last run), and no more than a daily budget of runs start in any
24 hours. These guards hold within one process: the API runs as a single replica (see
infra/main.bicep) so they hold for the deployment.

Each match keeps one feed log for the life of the matchday; a new run resets it, so readers that
opened the feed earlier follow the new run.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

from fourth_official_match_data import MatchStore
from fourth_official_replay.log import FeedLog
from fourth_official_replay.replay import Explainer, ReplayConfig, Sleep, replay

MatchState = Literal["idle", "running", "finished", "failed"]
DEFAULT_COOLDOWN_SECONDS = 15 * 60.0
DEFAULT_RUNS_PER_DAY = 24
DAY_SECONDS = 24 * 60 * 60.0


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
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._store, self._explainer, self._sleep = store, explainer, sleep
        self._config = config or ReplayConfig()
        self._cooldown, self._runs_per_day = cooldown, runs_per_day
        self._feeds = {match_id: FeedLog(match_id) for match_id in store.match_ids()}
        self._runs: dict[str, asyncio.Task[None]] = {}
        self._starts: list[float] = []
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

    def _check_can_start(self, now: float) -> None:
        if self.running:
            raise MatchdayBusyError("a matchday is already running")
        if self._starts and now - self._starts[-1] < self._cooldown:
            wait = int(self._cooldown - (now - self._starts[-1]))
            raise MatchdayBusyError(f"the matchday can be replayed again in {wait} seconds")
        if len([t for t in self._starts if now - t < DAY_SECONDS]) >= self._runs_per_day:
            raise MatchdayBusyError("the matchday has been replayed as often as allowed today")

    async def start(self, *, now: float | None = None) -> None:
        """Replay every match from the start. Refuses while a run is under way, during the
        cooldown, and beyond the daily budget."""
        moment = time.monotonic() if now is None else now
        async with self._lock:
            self._check_can_start(moment)
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
            self._starts = [*self._starts, moment][-self._runs_per_day :]

    async def wait(self) -> None:
        """Wait for the current run to end, however it ends."""
        await asyncio.gather(*self._runs.values(), return_exceptions=True)

    async def stop(self) -> None:
        """Cancel a run under way (on shutdown) and wait for it to wind down."""
        for run in self._runs.values():
            run.cancel()
        await self.wait()
