"""The matchday: the demo's matches, replayed together, one run at a time.

A run spends model tokens, so only one runs at a time, and runs start at most once per cooldown
(counted from the start of the last run). Each run starts every match's feed afresh.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

from fourth_official_match_data import MatchStore
from fourth_official_replay.log import FeedLog
from fourth_official_replay.replay import Explainer, ReplayConfig, Sleep, replay

MatchState = Literal["idle", "running", "finished"]
DEFAULT_COOLDOWN_SECONDS = 15 * 60.0


class MatchdayBusyError(RuntimeError):
    """A run is under way, or the last one started too recently. The message is safe to show."""


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
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._store, self._explainer, self._sleep = store, explainer, sleep
        self._config = config or ReplayConfig()
        self._cooldown = cooldown
        self._feeds = {match_id: FeedLog(match_id) for match_id in store.match_ids()}
        self._runs: dict[str, asyncio.Task[None]] = {}
        self._last_start: float | None = None
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
        return "finished" if run.done() else "running"

    @property
    def running(self) -> bool:
        return any(not run.done() for run in self._runs.values())

    async def start(self, *, now: float | None = None) -> None:
        """Replay every match from the start. Refuses while a run is under way or cooling down."""
        moment = time.monotonic() if now is None else now
        async with self._lock:
            if self.running:
                raise MatchdayBusyError("a matchday is already running")
            if self._last_start is not None and moment - self._last_start < self._cooldown:
                wait = int(self._cooldown - (moment - self._last_start))
                raise MatchdayBusyError(f"the matchday can be replayed again in {wait} seconds")
            self._feeds = {match_id: FeedLog(match_id) for match_id in self._store.match_ids()}
            self._runs = {
                match_id: asyncio.create_task(
                    replay(
                        self._store.record(match_id),
                        feed,
                        self._explainer,
                        config=self._config,
                        sleep=self._sleep,
                    ),
                    name=f"replay-{match_id}",
                )
                for match_id, feed in self._feeds.items()
            }
            self._last_start = moment

    async def wait(self) -> None:
        """Wait for the current run to finish."""
        await asyncio.gather(*self._runs.values())

    async def stop(self) -> None:
        """Cancel a run under way (on shutdown) and wait for it to wind down."""
        for run in self._runs.values():
            run.cancel()
        await asyncio.gather(*self._runs.values(), return_exceptions=True)
