"""Deciding a held item during the match: the decision is the item's next entry on the match's
feed, so every partner screen and stream sees it at once."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import anyio
import pytest

from fourth_official_contracts import ClockEntry, MatchClock, TenantItemEntry
from fourth_official_match_data import demo_store
from fourth_official_replay import Matchday, ReplayConfig
from fourth_official_replay.matchday import UnknownItemError
from fourth_official_replay.partners import DecisionError
from test_matchday import no_wait, template_only
from test_partners import partners

NOW = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)


def instant(clock: MatchClock) -> int:
    return clock.period * 10_000 + clock.minute * 60 + clock.second


class Paused:
    """Plays the featured match, then waits before full time until released: its held items are
    on the feed and the feed is still open."""

    def __init__(self) -> None:
        self.day = Matchday(
            demo_store(),
            template_only,
            config=ReplayConfig(),
            sleep=no_wait,
            partners=partners,
        )
        self.released = anyio.Event()
        feed = self.day.feed("m42")
        finish = feed.finish

        async def held_open() -> None:
            await self.released.wait()
            await finish()

        feed.finish = held_open  # type: ignore[method-assign]

    def held(self) -> list[TenantItemEntry]:
        return [
            e
            for e in self.day.feed("m42").entries
            if isinstance(e, TenantItemEntry) and e.state == "pending_approval"
        ]


def during_the_match(check: Callable[[Paused], Awaitable[None]]) -> None:
    paused = Paused()

    async def run() -> None:
        await paused.day.start(now=0.0)
        with anyio.fail_after(10):
            while not paused.held():
                await anyio.sleep(0)
        await check(paused)
        paused.released.set()
        await paused.day.wait()

    anyio.run(run)


def test_an_approval_is_published_on_the_feed_at_the_match_clock() -> None:
    async def check(paused: Paused) -> None:
        item = paused.held()[0]
        entries_before = len(paused.day.feed("m42").entries)
        clock = [e for e in paused.day.feed("m42").entries if isinstance(e, ClockEntry)][-1]

        entry = await paused.day.decide(
            "m42", item.tenant_id, item.overlay.item_id, "approved", reason=None, now=NOW
        )

        assert entry.state == "on_air"
        assert entry.entry_seq == entries_before + 1
        assert paused.day.feed("m42").entries[-1] == entry
        assert instant(entry.overlay.in_at) >= instant(clock.clock)

    during_the_match(check)


def test_an_item_is_decided_once() -> None:
    async def check(paused: Paused) -> None:
        item = paused.held()[0]
        await paused.day.decide(
            "m42", item.tenant_id, item.overlay.item_id, "rejected", reason="Off tone", now=NOW
        )

        with pytest.raises(DecisionError, match="not awaiting"):
            await paused.day.decide(
                "m42", item.tenant_id, item.overlay.item_id, "approved", reason=None, now=NOW
            )

    during_the_match(check)


def test_two_editors_deciding_at_once_cannot_both_win() -> None:
    async def check(paused: Paused) -> None:
        item = paused.held()[0]
        outcomes: list[str] = []

        async def attempt(decision: str) -> None:
            try:
                await paused.day.decide(
                    "m42",
                    item.tenant_id,
                    item.overlay.item_id,
                    decision,  # type: ignore[arg-type]
                    reason="Off tone" if decision == "rejected" else None,
                    now=NOW,
                )
                outcomes.append(decision)
            except DecisionError:
                outcomes.append("refused")

        async with anyio.create_task_group() as group:
            group.start_soon(attempt, "approved")
            group.start_soon(attempt, "rejected")

        assert sorted(outcomes).count("refused") == 1

    during_the_match(check)


def test_an_unknown_item_or_match_is_not_found() -> None:
    async def check(paused: Paused) -> None:
        with pytest.raises(UnknownItemError):
            await paused.day.decide(
                "m42",
                "tribuna-austral",
                "it-tribuna-austral-nothing",
                "approved",
                reason=None,
                now=NOW,
            )
        with pytest.raises(UnknownItemError):
            await paused.day.decide(
                "m99", "tribuna-austral", "it-x", "approved", reason=None, now=NOW
            )

    during_the_match(check)


def test_after_full_time_a_held_item_can_no_longer_air() -> None:
    day = Matchday(
        demo_store(), template_only, config=ReplayConfig(), sleep=no_wait, partners=partners
    )

    async def run() -> None:
        await day.start(now=0.0)
        await day.wait()
        item = next(
            e
            for e in day.feed("m42").entries
            if isinstance(e, TenantItemEntry) and e.state == "pending_approval"
        )
        with pytest.raises(DecisionError, match="full time"):
            await day.decide(
                "m42", item.tenant_id, item.overlay.item_id, "approved", reason=None, now=NOW
            )

    anyio.run(run)
