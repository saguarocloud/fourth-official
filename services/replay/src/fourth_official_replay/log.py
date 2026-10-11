"""The feed log of one match: append-only within a run, numbered in order, and something clients
can wait on.

The log object lives as long as the matchday. Each new run resets it to a new generation, waking
every reader, so a client that opened the feed before a run started (or during an earlier run)
always follows the current one.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from fourth_official_contracts import FeedEntry


class FeedFinishedError(RuntimeError):
    """The run is over: nothing more is published on this feed until the next run."""


class StaleRunError(RuntimeError):
    """An entry built for an earlier run of the matchday."""


@dataclass(frozen=True, slots=True)
class FeedView:
    """What a reader sees: the run (generation) it belongs to, entries, and whether it is done."""

    generation: int
    entries: tuple[FeedEntry, ...]
    finished: bool


class FeedLog:
    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        self._entries: list[FeedEntry] = []
        self._changed = asyncio.Condition()
        self._finished = False
        self._generation = 0

    @property
    def entries(self) -> tuple[FeedEntry, ...]:
        return tuple(self._entries)

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def generation(self) -> int:
        return self._generation

    def since(self, entry_seq: int) -> tuple[FeedEntry, ...]:
        """Entries after `entry_seq`, in order."""
        return tuple(self._entries[max(entry_seq, 0) :])

    def view(self, after: int) -> FeedView:
        return FeedView(self._generation, self.since(after), self._finished)

    async def reset(self) -> None:
        """Start a new run: empty the log, open it again, and wake every reader."""
        async with self._changed:
            self._generation += 1
            self._entries = []
            self._finished = False
            self._changed.notify_all()

    async def publish(
        self,
        build: Callable[[int], FeedEntry],
        *,
        generation: int | None = None,
        guard: Callable[[tuple[FeedEntry, ...]], None] | None = None,
    ) -> FeedEntry:
        """Append the entry `build` makes for the next number, and wake every waiting reader.
        With `generation`, the entry is refused if a new run has started since; with `guard`,
        if it raises on the entries as they stand at the moment of appending (a compare and
        swap: nothing can slip in between the check and the append)."""
        async with self._changed:
            if generation is not None and generation != self._generation:
                raise StaleRunError(f"the feed of {self.match_id} has started a new run")
            if guard is not None:
                guard(tuple(self._entries))
            if self._finished:
                raise FeedFinishedError(f"the feed of {self.match_id} is finished")
            number = len(self._entries) + 1
            entry = build(number)
            if entry.match_id != self.match_id:
                raise ValueError(f"this is the feed of {self.match_id}")
            if entry.entry_seq != number:
                raise ValueError(f"entries are numbered in order: expected {number}")
            self._entries.append(entry)
            self._changed.notify_all()
        return entry

    async def finish(self) -> None:
        """No more entries will come in this run: wake every waiting reader."""
        async with self._changed:
            self._finished = True
            self._changed.notify_all()

    async def wait_beyond(self, generation: int, entry_seq: int, *, timeout: float) -> FeedView:
        """Entries after `entry_seq` of `generation`, waiting up to `timeout` seconds for some to
        arrive. Returns at once with the current view if a new run has started."""
        async with self._changed:
            try:
                async with asyncio.timeout(timeout):
                    await self._changed.wait_for(
                        lambda: (
                            self._generation != generation
                            or len(self._entries) > entry_seq
                            or self._finished
                        )
                    )
            except TimeoutError:
                pass
            if self._generation != generation:
                return self.view(0)
            return self.view(entry_seq)
