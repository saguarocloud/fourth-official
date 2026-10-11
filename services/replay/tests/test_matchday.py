"""The matchday: starts the demo's replays, one run at a time, and serves each match's feed."""

from collections.abc import Callable

import anyio
import pytest

from fourth_official_contracts import InsightEntry, Moment
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_replay import Availability, InMemoryLedger, Matchday, ReplayConfig
from fourth_official_replay.matchday import MatchdayBusyError
from fourth_official_verifier import MatchFacts
from test_partners import partners


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


def test_the_guards_read_starts_from_the_ledger_so_a_durable_one_survives_restarts() -> None:
    shared = InMemoryLedger()

    async def run() -> None:
        first = Matchday(demo_store(), template_only, sleep=no_wait, ledger=shared)
        await first.start(now=1_000.0)
        await first.wait()
        # A new process (a replica that scaled to zero and back) with the same ledger.
        second = Matchday(demo_store(), template_only, sleep=no_wait, ledger=shared)
        with pytest.raises(MatchdayBusyError, match="again in"):
            await second.start(now=1_100.0)

    anyio.run(run)


def test_availability_says_when_the_next_run_may_start() -> None:
    day = matchday(cooldown=600.0, runs_per_day=2)

    async def run() -> list[Availability]:
        seen = [await day.availability(now=0.0)]
        await day.start(now=0.0)
        seen.append(await day.availability(now=1.0))
        await day.wait()
        seen.append(await day.availability(now=100.0))
        await day.start(now=700.0)
        await day.wait()
        seen.append(await day.availability(now=1400.0))
        return seen

    idle, running, cooling, spent = anyio.run(run)

    assert idle == Availability(ready=True)
    assert running == Availability(
        ready=False, blocked_by="running", reason="a matchday is already running"
    )
    assert cooling == Availability(
        ready=False,
        blocked_by="cooldown",
        reason="the matchday can be replayed again in 500 seconds",
        ready_at=600.0,
    )
    assert spent.blocked_by == "daily_limit"
    assert spent.ready_at == 24 * 60 * 60.0


def test_when_the_cooldown_ends_inside_a_spent_day_the_day_decides() -> None:
    day = matchday(cooldown=600.0, runs_per_day=2)

    async def run() -> Availability:
        for now in (0.0, 700.0):
            await day.start(now=now)
            await day.wait()
        blocked = await day.availability(now=800.0)
        assert blocked.ready_at is not None
        await day.start(now=blocked.ready_at)  # a run starts exactly when promised
        await day.wait()
        return blocked

    blocked = anyio.run(run)

    assert blocked.blocked_by == "daily_limit"
    assert blocked.ready_at == 24 * 60 * 60.0


def test_a_start_is_claimed_against_the_starts_the_ledger_holds_at_that_moment() -> None:
    class LateLedger(InMemoryLedger):
        """Another process records a start just before this one claims."""

        async def claim(self, started: float, check: Callable[[tuple[float, ...]], None]) -> None:
            await super().claim(started - 1.0, lambda _: None)
            await super().claim(started, check)

    day = Matchday(demo_store(), template_only, sleep=no_wait, cooldown=600.0, ledger=LateLedger())

    async def run() -> None:
        await day.start(now=1000.0)

    with pytest.raises(MatchdayBusyError, match="again in"):
        anyio.run(run)
    assert [m.state for m in day.status()] == ["idle"] * 3


def test_with_partners_each_run_publishes_partner_items_with_fresh_schedules() -> None:
    made: list[object] = []

    def factory() -> object:
        made.append(partners())
        return made[-1]

    day = Matchday(
        demo_store(),
        template_only,
        sleep=no_wait,
        cooldown=0.0,
        partners=factory,  # type: ignore[arg-type]
    )

    async def run() -> None:
        await day.start(now=0.0)
        await day.wait()

    anyio.run(run)

    kinds = {getattr(e, "tenant_id", None) for e in day.feed("m42").entries}
    assert {"northlight-sport", "tribuna-austral", "rheinblick-sport"} <= kinds
    assert len(made) == 3  # one per match
