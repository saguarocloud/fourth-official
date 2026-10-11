"""Replaying a match publishes its clock, moments, verified insights and corrections, in order."""

import asyncio
import importlib
from functools import cache

import anyio
import pytest

from fourth_official_contracts import (
    Amendment,
    ClockEntry,
    CorrectionEntry,
    EventAmended,
    EventVoided,
    FeedEntry,
    GoalEvent,
    InsightEntry,
    Moment,
    MomentEntry,
    parse_feed_entry,
)
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_replay import FeedLog, ReplayConfig, replay
from fourth_official_replay.replay import correction_board, correction_summary
from fourth_official_verifier import MatchFacts

replay_module = importlib.import_module("fourth_official_replay.replay")
PAUSES: dict[str, list[float]] = {}


async def no_wait(seconds: float) -> None:
    return None


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


@cache
def featured() -> tuple[FeedEntry, ...]:
    record = demo_store().record("m42")
    log = FeedLog("m42")

    pauses = PAUSES.setdefault("featured", [])

    async def record_pause(seconds: float) -> None:
        pauses.append(seconds)

    async def run() -> None:
        await replay(record, log, template_only, config=ReplayConfig(speed=8.0), sleep=record_pause)

    anyio.run(run)
    return log.entries


def of[E](kind: type[E]) -> list[E]:
    return [e for e in featured() if isinstance(e, kind)]


def test_entries_are_numbered_in_order_and_valid_on_the_wire() -> None:
    entries = featured()

    assert [e.entry_seq for e in entries] == list(range(1, len(entries) + 1))
    for entry in entries:
        assert parse_feed_entry(entry.to_wire()) == entry


def test_every_detected_moment_is_published_and_then_explained() -> None:
    moments = of(MomentEntry)
    insights = of(InsightEntry)

    assert {m.moment.moment_id for m in moments} == {i.insight.moment_id for i in insights}
    first_seen = {m.moment.moment_id: m.entry_seq for m in moments}
    assert all(i.entry_seq > first_seen[i.insight.moment_id] for i in insights)
    assert all(i.verdict.passed and i.rendered.claims for i in insights)


def test_the_clock_moves_forward_and_the_score_follows_the_goals() -> None:
    clocks = of(ClockEntry)
    record = demo_store().record("m42")
    goals = sum(isinstance(e, GoalEvent) for e in record.match.events)

    assert [c.as_of_seq for c in clocks] == sorted(c.as_of_seq for c in clocks)
    final = clocks[-1]
    assert final.as_of_seq == record.match.events[-1].seq
    assert (final.score.home, final.score.away) == (2, 1)
    assert goals == 4  # one of them was voided


def test_the_voided_goal_leaves_the_score_once_var_has_decided() -> None:
    record = demo_store().record("m42")
    (decided,) = record.void_seqs().values()
    clocks = of(ClockEntry)

    before = [c for c in clocks if c.as_of_seq < decided][-1]
    after = next(c for c in clocks if c.as_of_seq >= decided)
    assert (before.score.home, before.score.away) == (2, 0)
    assert (after.score.home, after.score.away) == (1, 0)


def test_corrections_are_published_when_they_are_issued() -> None:
    corrections = of(CorrectionEntry)
    record = demo_store().record("m42")

    assert [c.correction for c in corrections] == list(record.corrections)
    void, amendment = corrections
    last_clock = of(ClockEntry)[-1]
    assert void.entry_seq < last_clock.entry_seq < amendment.entry_seq


def test_replay_waits_scaled_and_capped_between_events() -> None:
    featured()
    config = ReplayConfig()
    pauses = PAUSES["featured"]

    assert pauses
    assert max(pauses) <= config.max_pause
    assert min(pauses) >= 0


def test_a_moment_that_cannot_be_explained_is_published_without_an_insight() -> None:
    record = demo_store().record("m42")
    log = FeedLog("m42")

    async def nothing(moment: Moment, facts: MatchFacts) -> Explanation:
        explained = await explain(moment, facts, [])
        return Explanation(moment, None, explained.verdict, explained.attempts)

    async def run() -> None:
        await replay(record, log, nothing, sleep=no_wait)

    anyio.run(run)

    assert any(isinstance(e, MomentEntry) for e in log.entries)
    assert not any(isinstance(e, InsightEntry) for e in log.entries)
    assert log.finished


def test_detecting_every_few_events_finds_the_same_moments_as_detecting_on_every_event() -> None:
    record = demo_store().record("m42")
    every = FeedLog("m42")

    async def run() -> None:
        await replay(
            record, every, template_only, config=ReplayConfig(detect_every=1), sleep=no_wait
        )

    anyio.run(run)

    def moments(entries: tuple[FeedEntry, ...]) -> list[Moment]:
        return [e.moment for e in entries if isinstance(e, MomentEntry)]

    assert moments(every.entries) == moments(featured())


def test_corrections_say_what_changed_in_words() -> None:
    void, amendment = of(CorrectionEntry)
    record = demo_store().record("m42")
    new_scorer = record.players[amendment.correction.changes.scorer_id or ""].name  # type: ignore[union-attr]

    assert void.summary == "Harbour City goal at 67' ruled out for offside"
    assert amendment.summary == f"Harbour City goal at 89' credited to {new_scorer}"


def test_a_correction_without_a_new_scorer_is_described_generically() -> None:
    record = demo_store().record("m42")
    goal = next(e for e in record.match.events if isinstance(e, GoalEvent))
    assist_removed = EventAmended(
        correction_id="c-m42-09",
        match_id="m42",
        reason="PROVIDER_RESTATEMENT",
        issued_at=goal.wall_clock,
        target_event_id=goal.event_id,
        new_version=2,
        kind="EVENT_AMENDED",
        changes=Amendment(assist_id=None),
    )

    assert correction_summary(record, assist_removed) == (
        f"Harbour City goal at {goal.clock.minute}' amended by the data provider"
    )


def test_a_failing_explanation_is_logged_and_the_match_carries_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    record = demo_store().record("m42")
    log = FeedLog("m42")
    calls: list[str] = []

    async def flaky(moment: Moment, facts: MatchFacts) -> Explanation:
        calls.append(moment.moment_id)
        if len(calls) == 1:
            raise RuntimeError("model unavailable")
        return await template_only(moment, facts)

    async def run() -> None:
        await replay(record, log, flaky, sleep=no_wait)

    anyio.run(run)

    moments = [e for e in log.entries if isinstance(e, MomentEntry)]
    insights = [e for e in log.entries if isinstance(e, InsightEntry)]
    assert len(insights) == len(moments) - 1
    assert log.finished
    assert any("failed" in r.getMessage() for r in caplog.records)


def test_cancelling_a_replay_leaves_no_explanation_running() -> None:
    record = demo_store().record("m42")
    log = FeedLog("m42")

    async def slow_explainer(moment: Moment, facts: MatchFacts) -> Explanation:
        await anyio.sleep(30)
        return await template_only(moment, facts)

    async def scenario() -> int:
        task = asyncio.create_task(replay(record, log, slow_explainer, sleep=no_wait))
        while not any(isinstance(e, MomentEntry) for e in log.entries):
            await asyncio.sleep(0)
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return len([t for t in asyncio.all_tasks() if t is not asyncio.current_task()])

    assert asyncio.run(scenario()) == 0
    assert log.finished


def test_a_failure_publishing_one_insight_stays_with_that_moment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = demo_store().record("m42")
    log = FeedLog("m42")
    real = replay_module.render_insight
    calls: list[int] = []

    def flaky_render(*args: object, **kwargs: object) -> object:
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("render failed")
        return real(*args, **kwargs)

    monkeypatch.setattr(replay_module, "render_insight", flaky_render)

    async def run() -> None:
        await replay(record, log, template_only, sleep=no_wait)

    anyio.run(run)

    moments = [e for e in log.entries if isinstance(e, MomentEntry)]
    insights = [e for e in log.entries if isinstance(e, InsightEntry)]
    assert len(insights) == len(moments) - 1
    assert log.finished


def test_a_correction_about_an_unknown_event_is_described_generically() -> None:
    record = demo_store().record("m42")
    stray = EventAmended(
        correction_id="c-m42-09",
        match_id="m42",
        reason="PROVIDER_RESTATEMENT",
        issued_at=record.match.events[0].wall_clock,
        target_event_id="m42-e9999",
        new_version=2,
        kind="EVENT_AMENDED",
        changes=Amendment(assist_id=None),
    )

    assert correction_summary(record, stray) == "An event amended by the data provider"


def test_corrections_light_the_out_in_board() -> None:
    void, amendment = of(CorrectionEntry)
    record = demo_store().record("m42")
    goal = next(
        e for e in record.match.events if e.event_id == amendment.correction.target_event_id
    )
    assert isinstance(goal, GoalEvent)
    assert isinstance(amendment.correction, EventAmended)
    old = record.players[goal.scorer_id]
    new = record.players[amendment.correction.changes.scorer_id or ""]

    assert (void.out_text, void.in_text) == ("2-0", "1-0")
    assert (amendment.out_text, amendment.in_text) == (
        f"HCY {old.shirt:02d}",
        f"HCY {new.shirt:02d}",
    )


def test_boards_for_unusual_corrections_still_light() -> None:
    record = demo_store().record("m42")
    issued = record.match.events[0].wall_clock
    unknown_void = EventVoided(
        correction_id="c-m42-08",
        match_id="m42",
        reason="PROVIDER_RESTATEMENT",
        issued_at=issued,
        target_event_id="m42-e9999",
        new_version=2,
        kind="EVENT_VOIDED",
    )
    goal = next(e for e in record.match.events if isinstance(e, GoalEvent))
    assist_removed = EventAmended(
        correction_id="c-m42-09",
        match_id="m42",
        reason="PROVIDER_RESTATEMENT",
        issued_at=issued,
        target_event_id=goal.event_id,
        new_version=2,
        kind="EVENT_AMENDED",
        changes=Amendment(assist_id=None),
    )

    assert correction_board(record, unknown_void) == ("EVENT", "VOID")
    assert correction_board(record, assist_removed) == ("AS PUBLISHED", "AMENDED")
