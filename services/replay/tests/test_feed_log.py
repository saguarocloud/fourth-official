"""The feed log: append-only within a run, numbered, reset per run, something clients wait on."""

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
        await log.publish(clock)
        await log.publish(clock)

    anyio.run(publish)

    assert [e.entry_seq for e in log.entries] == [1, 2]
    assert [e.entry_seq for e in log.since(1)] == [2]
    assert log.since(2) == ()


def test_an_entry_for_another_match_out_of_order_or_after_the_end_is_refused() -> None:
    with pytest.raises(ValueError, match="m43"):
        anyio.run(FeedLog("m43").publish, clock)
    with pytest.raises(ValueError, match="numbered"):
        anyio.run(FeedLog("m42").publish, lambda n: clock(n + 1))

    finished = FeedLog("m42")
    anyio.run(finished.finish)
    with pytest.raises(RuntimeError, match="finished"):
        anyio.run(finished.publish, clock)


def test_a_waiting_reader_wakes_when_an_entry_arrives_and_otherwise_times_out() -> None:
    log = FeedLog("m42")

    async def scenario() -> tuple[int, ...]:
        woken: list[int] = []
        waiting = anyio.Event()

        async def reader() -> None:
            waiting.set()
            view = await log.wait_beyond(0, 0, timeout=5)
            woken.extend(e.entry_seq for e in view.entries)

        async with anyio.create_task_group() as group:
            group.start_soon(reader)
            await waiting.wait()
            await anyio.lowlevel.checkpoint()
            await log.publish(clock)
        idle = await log.wait_beyond(0, 1, timeout=0.01)
        assert idle.entries == ()
        return tuple(woken)

    assert anyio.run(scenario) == (1,)


def test_a_new_run_wakes_readers_of_the_old_one_with_a_fresh_view() -> None:
    log = FeedLog("m42")

    async def scenario() -> tuple[int, int]:
        await log.publish(clock)
        await log.publish(clock)
        result: list[tuple[int, int]] = []
        waiting = anyio.Event()

        async def reader() -> None:
            waiting.set()
            view = await log.wait_beyond(0, 2, timeout=5)
            result.append((view.generation, len(view.entries)))

        async with anyio.create_task_group() as group:
            group.start_soon(reader)
            await waiting.wait()
            await anyio.lowlevel.checkpoint()
            await log.reset()
        return result[0]

    assert anyio.run(scenario) == (1, 0)
    assert log.entries == ()
    assert not log.finished


def test_finishing_wakes_waiters_and_marks_the_run_done() -> None:
    log = FeedLog("m42")

    async def scenario() -> bool:
        waiting = anyio.Event()
        seen: list[bool] = []

        async def reader() -> None:
            waiting.set()
            seen.append((await log.wait_beyond(0, 0, timeout=5)).finished)

        async with anyio.create_task_group() as group:
            group.start_soon(reader)
            await waiting.wait()
            await anyio.lowlevel.checkpoint()
            await log.finish()
        return seen[0]

    assert anyio.run(scenario) is True
