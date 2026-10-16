"""The feed log: append-only within a run, numbered, reset per run, something clients wait on."""

from collections.abc import Callable

import anyio
import pytest

from fourth_official_contracts import ClockEntry, MatchClock, Score
from fourth_official_replay import FeedLog
from fourth_official_replay.log import FeedFinishedError, StaleRunError


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


def test_an_entry_meant_for_an_earlier_run_is_refused() -> None:
    log = FeedLog("m42")
    anyio.run(log.reset)

    with pytest.raises(StaleRunError):
        anyio.run(lambda: log.publish(clock, generation=log.generation - 1))
    anyio.run(lambda: log.publish(clock, generation=log.generation))
    assert len(log.entries) == 1


def test_a_finished_feed_says_so_in_its_own_error() -> None:
    log = FeedLog("m42")
    anyio.run(log.finish)

    with pytest.raises(FeedFinishedError):
        anyio.run(log.publish, clock)


def test_a_guarded_entry_is_appended_only_if_the_log_still_allows_it() -> None:
    log = FeedLog("m42")

    def refuse(entries: tuple[object, ...]) -> None:
        raise LookupError("changed since")

    with pytest.raises(LookupError, match="changed since"):
        anyio.run(lambda: log.publish(clock, guard=refuse))
    assert log.entries == ()
    anyio.run(lambda: log.publish(clock, guard=lambda entries: None))
    assert len(log.entries) == 1


def ticking() -> Callable[[], float]:
    """A clock that reads 0.0, 0.5, 1.0, … seconds, one step per reading."""
    readings = iter(n * 0.5 for n in range(1000))
    return lambda: next(readings)


def test_the_log_times_each_entry_and_each_event_played_in_the_run() -> None:
    log = FeedLog("m42", clock=ticking())

    async def run() -> None:  # the log was made at 0.0
        await log.reset()  # the run starts at 0.5
        log.played(7)  # 1.0
        await log.publish(clock)  # 1.5
        log.played(8)  # 2.0
        await log.publish(clock)  # 2.5

    anyio.run(run)

    timing = log.timing
    assert timing.started == 0.5
    assert timing.published == (1.5, 2.5)
    assert timing.played == {7: 1.0, 8: 2.0}


def test_a_new_run_starts_its_timing_afresh() -> None:
    log = FeedLog("m42", clock=ticking())

    async def two_runs() -> None:
        await log.reset()
        log.played(7)
        await log.publish(clock)
        await log.reset()

    anyio.run(two_runs)

    assert log.timing.published == ()
    assert log.timing.played == {}
    assert log.timing.started == 2.0


def test_an_event_keeps_the_time_it_was_first_played() -> None:
    log = FeedLog("m42", clock=ticking())
    log.played(7)
    log.played(7)

    assert log.timing.played == {7: 0.5}


def test_the_log_reads_its_own_clock_for_whoever_measures_its_run() -> None:
    log = FeedLog("m42", clock=ticking())

    assert log.now() == 0.5


def test_a_snapshot_pairs_every_entry_with_the_time_it_was_published() -> None:
    log = FeedLog("m42", clock=ticking())

    async def run() -> None:
        await log.reset()
        await log.publish(clock)
        await log.publish(clock)

    anyio.run(run)

    entries, timing = log.snapshot()
    assert [e.entry_seq for e in entries] == [1, 2]
    assert len(timing.published) == len(entries)
