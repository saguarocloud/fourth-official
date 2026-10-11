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


def matchday(**options: float) -> Matchday:
    return Matchday(demo_store(), template_only, config=ReplayConfig(), sleep=no_wait, **options)


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


def test_a_restart_begins_a_fresh_feed() -> None:
    day = matchday(cooldown=0.0)

    async def run() -> int:
        await day.start(now=0.0)
        await day.wait()
        first = len(day.feed("m42").entries)
        await day.start(now=1.0)
        await day.wait()
        return first

    first = anyio.run(run)

    assert len(day.feed("m42").entries) == first


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
