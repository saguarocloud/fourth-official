"""The feed log: append-only, numbered, and something a client can wait on."""

import anyio
import pytest

from fourth_official_contracts import ClockEntry, MatchClock, Score
from fourth_official_replay import FeedLog


def clock(entry_seq: int, as_of_seq: int = 1) -> ClockEntry:
    return ClockEntry(
        kind="clock",
        entry_seq=entry_seq,
        match_id="m42",
        as_of_seq=as_of_seq,
        clock=MatchClock(period=1, minute=1, second=0),
        score=Score(home=0, away=0),
    )


def test_entries_are_numbered_as_they_are_published() -> None:
    log = FeedLog("m42")

    async def publish() -> None:
        await log.publish(lambda n: clock(n, as_of_seq=10))
        await log.publish(lambda n: clock(n, as_of_seq=20))

    anyio.run(publish)

    assert [e.entry_seq for e in log.entries] == [1, 2]
    assert [e.entry_seq for e in log.since(1)] == [2]
    assert log.since(2) == ()


def test_an_entry_for_another_match_or_out_of_order_is_refused() -> None:
    log = FeedLog("m43")

    with pytest.raises(ValueError, match="m43"):
        anyio.run(log.publish, clock)
    with pytest.raises(ValueError, match="numbered"):
        anyio.run(FeedLog("m42").publish, lambda n: clock(n + 1))


def test_a_waiting_client_wakes_when_an_entry_arrives_or_times_out() -> None:
    log = FeedLog("m42")
    woken: list[int] = []

    async def scenario() -> None:
        async def client() -> None:
            woken.extend(e.entry_seq for e in await log.wait_beyond(0, timeout=5))

        async with anyio.create_task_group() as group:
            group.start_soon(client)
            await anyio.sleep(0.01)
            await log.publish(clock)
        assert await log.wait_beyond(1, timeout=0.01) == ()

    anyio.run(scenario)

    assert woken == [1]


def test_finishing_wakes_waiters_and_marks_the_log_done() -> None:
    log = FeedLog("m42")

    async def scenario() -> tuple[object, ...]:
        async with anyio.create_task_group() as group:
            result: list[tuple[object, ...]] = []

            async def client() -> None:
                result.append(await log.wait_beyond(0, timeout=5))

            group.start_soon(client)
            await anyio.sleep(0.01)
            await log.finish()
        return result[0]

    assert anyio.run(scenario) == ()
    assert log.finished
