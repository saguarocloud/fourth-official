"""The matchday: starts the demo's replays, one run at a time, and serves each match's feed."""

import anyio
import pytest

from fourth_official_contracts import InsightEntry, Moment
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_replay import Matchday, ReplayConfig
from fourth_official_replay.matchday import MatchdayBusyError
from fourth_official_verifier import MatchFacts


async def no_wait(seconds: float) -> None:
    return None


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


def matchday(*, cooldown: float = 15 * 60.0, runs_per_day: int = 24) -> Matchday:
    return Matchday(
        demo_store(),
        template_only,
        config=ReplayConfig(),
        sleep=no_wait,
        cooldown=cooldown,
        runs_per_day=runs_per_day,
    )


def test_before_it_starts_every_match_is_listed_and_idle() -> None:
    day = matchday()

    assert [(m.match_id, m.state) for m in day.status()] == [
        ("m42", "idle"),
        ("m43", "idle"),
        ("m44", "idle"),
    ]
    assert day.feed("m42").entries == ()


def test_starting_replays_every_match_to_the_end() -> None:
    day = matchday()

    async def run() -> None:
        await day.start(now=0.0)
        await day.wait()

    anyio.run(run)

    assert [m.state for m in day.status()] == ["finished"] * 3
    assert any(isinstance(e, InsightEntry) for e in day.feed("m42").entries)


def test_only_one_run_at_a_time_and_a_cooldown_after_it() -> None:
    day = matchday(cooldown=600.0)

    async def run() -> None:
        await day.start(now=0.0)
        with pytest.raises(MatchdayBusyError, match="already running"):
            await day.start(now=1.0)
        await day.wait()
        with pytest.raises(MatchdayBusyError, match="again in 500 seconds"):
            await day.start(now=100.0)
        await day.start(now=700.0)
        await day.wait()

    anyio.run(run)

    assert [m.state for m in day.status()] == ["finished"] * 3


def test_a_restart_resets_the_same_feed_so_readers_follow_the_new_run() -> None:
    day = matchday(cooldown=0.0)
    feed = day.feed("m42")

    async def run() -> tuple[int, int]:
        await day.start(now=0.0)
        await day.wait()
        first = (feed.generation, len(feed.entries))
        await day.start(now=1.0)
        await day.wait()
        return first

    first_generation, first_entries = anyio.run(run)

    assert day.feed("m42") is feed
    assert feed.generation == first_generation + 1
    assert len(feed.entries) == first_entries


def test_a_reader_waiting_before_the_first_run_follows_it() -> None:
    day = matchday()
    feed = day.feed("m42")

    async def scenario() -> int:
        seen: list[int] = []
        waiting = anyio.Event()

        async def reader() -> None:
            waiting.set()
            view = await feed.wait_beyond(feed.generation, 0, timeout=10)
            seen.append(view.generation)

        async with anyio.create_task_group() as group:
            group.start_soon(reader)
            await waiting.wait()
            await anyio.lowlevel.checkpoint()
            await day.start(now=0.0)
        await day.wait()
        return seen[0]

    assert anyio.run(scenario) == 1


def test_a_run_that_crashes_is_reported_as_failed() -> None:
    async def broken_sleep(seconds: float) -> None:
        raise RuntimeError("clock failure")

    day = Matchday(demo_store(), template_only, sleep=broken_sleep)

    async def run() -> None:
        await day.start(now=0.0)
        await day.wait()

    anyio.run(run)

    assert [m.state for m in day.status()] == ["failed"] * 3


def test_no_more_than_the_daily_budget_of_runs_start() -> None:
    day = matchday(cooldown=0.0, runs_per_day=2)

    async def run() -> None:
        for now in (0.0, 1.0):
            await day.start(now=now)
            await day.wait()
        with pytest.raises(MatchdayBusyError, match="as often as allowed today"):
            await day.start(now=2.0)
        await day.start(now=2.0 + 24 * 60 * 60)
        await day.wait()

    anyio.run(run)


def test_an_unknown_match_has_no_feed() -> None:
    with pytest.raises(KeyError):
        matchday().feed("m99")


def test_stopping_cancels_a_run_under_way() -> None:
    async def slow(seconds: float) -> None:
        await anyio.sleep(1)

    day = Matchday(demo_store(), template_only, sleep=slow)

    async def run() -> None:
        await day.start(now=0.0)
        await anyio.sleep(0.05)
        await day.stop()

    anyio.run(run)

    assert not day.running
    assert all(day.feed(m.match_id).finished for m in day.status())
