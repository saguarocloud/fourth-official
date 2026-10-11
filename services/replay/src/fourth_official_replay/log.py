"""The feed log of one match: append-only, numbered in order, and something clients can wait on."""

import asyncio
from collections.abc import Callable

from fourth_official_contracts import FeedEntry


class FeedLog:
    """Entries are only ever appended, each numbered one more than the last. Readers ask for the
    entries after a number they already have, or wait until there are some."""

    def __init__(self, match_id: str) -> None:
        self.match_id = match_id
        self._entries: list[FeedEntry] = []
        self._changed = asyncio.Condition()
        self._finished = False

    @property
    def entries(self) -> tuple[FeedEntry, ...]:
        return tuple(self._entries)

    @property
    def finished(self) -> bool:
        return self._finished

    def since(self, entry_seq: int) -> tuple[FeedEntry, ...]:
        """Entries after `entry_seq`, in order."""
        return tuple(self._entries[max(entry_seq, 0) :])

    async def publish(self, build: Callable[[int], FeedEntry]) -> FeedEntry:
        """Append the entry `build` makes for the next number, and wake every waiting reader."""
        async with self._changed:
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
        """No more entries will come: wake every waiting reader."""
        async with self._changed:
            self._finished = True
            self._changed.notify_all()

    async def wait_beyond(self, entry_seq: int, *, timeout: float) -> tuple[FeedEntry, ...]:
        """Entries after `entry_seq`, waiting up to `timeout` seconds for some to arrive."""
        async with self._changed:
            try:
                async with asyncio.timeout(timeout):
                    await self._changed.wait_for(
                        lambda: len(self._entries) > entry_seq or self._finished
                    )
            except TimeoutError:
                pass
            return self.since(entry_seq)
