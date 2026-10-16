"""A run's operations, from its feed and its log's timing: latency, fallbacks, corrections."""

import dataclasses
from functools import cache

import anyio
import pytest

from fourth_official_contracts import (
    CorrectionReportEntry,
    InsightEntry,
    Moment,
    MomentEntry,
    Spread,
    TenantId,
    TenantItemEntry,
    TokenUse,
)
from fourth_official_contracts.scorecard import Ratio
from fourth_official_explain import Explanation, explain
from fourth_official_explain.pipeline import Attempt
from fourth_official_explain.production import PRICES
from fourth_official_match_data import demo_store
from fourth_official_replay import FeedLog, fixed_clocks, replay
from fourth_official_replay.operations import (
    COSTS,
    TARGETS,
    Measured,
    Targets,
    measure,
    percentile,
    report,
    spread,
)
from fourth_official_verifier import MatchFacts
from test_partners import partners

STEP = 0.25  # seconds between two readings of the test clock


async def no_wait(seconds: float) -> None:
    return None


async def model_then_template(moment: Moment, facts: MatchFacts) -> Explanation:
    """The template's insight, reached after a model failed once and was refused once."""
    explanation = await explain(moment, facts, [])
    template = explanation.attempts[-1]
    tried = (
        Attempt(1, "analyst", "fast", "error", error="TimeoutError", input_tokens=4000),
        Attempt(
            2,
            "analyst",
            "fallback",
            "failed",
            ("UNSUPPORTED_CLAIM",),
            input_tokens=1500,
            output_tokens=200,
        ),
    )
    return dataclasses.replace(
        explanation, attempts=(*tried, dataclasses.replace(template, number=3))
    )


@cache
def run(*, with_models: bool = False) -> FeedLog:
    """The featured match with partners, timed by a clock that ticks STEP on every reading."""
    readings = iter(range(10_000_000))
    log = FeedLog("m42", clock=lambda: next(readings) * STEP)
    explainer = model_then_template if with_models else template_only

    async def play() -> None:
        await log.reset()
        await replay(
            demo_store().record("m42"),
            log,
            explainer,
            sleep=no_wait,
            partners=partners(),
            clocks=fixed_clocks(),
        )

    anyio.run(play)
    return log


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


def finished(log: FeedLog, now: float = 1e9) -> Measured:
    return measure("m42", "finished", log.entries, log.timing, now=now)


def test_percentiles_are_nearest_rank() -> None:
    values = list(range(1, 101))

    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95
    assert percentile([7], 95) == 7
    assert percentile([30, 10, 20], 50) == 20


def test_a_spread_of_nothing_has_no_percentiles() -> None:
    assert spread([]).p50_ms is None
    assert spread([4, 1, 9]) == Spread(count=3, p50_ms=4, p95_ms=9)


def test_every_partner_item_aired_without_an_editor_is_timed_from_its_event() -> None:
    log = run()
    measured = finished(log)
    items = [
        e
        for e in log.entries
        if isinstance(e, TenantItemEntry) and e.localized is not None and e.localized.version == 1
    ]

    for partner in measured.match.partners:
        mine = [e for e in items if e.tenant_id == partner.tenant_id]
        assert partner.items == len({e.overlay.item_id for e in mine})
        assert partner.held == sum(e.state == "pending_approval" for e in mine)
        assert partner.on_air.count == sum(e.state == "on_air" for e in mine)
        assert partner.within_target.of == partner.on_air.count
    assert {p.tenant_id for p in measured.match.partners} == {e.tenant_id for e in items}
    # Every duration is a whole number of clock steps, and never negative.
    assert all(d % int(STEP * 1000) == 0 and d > 0 for d in measured.on_air)


def test_an_item_is_timed_from_the_last_event_its_insight_rests_on() -> None:
    log = run()
    timing = log.timing
    stamps = dict(zip((e.entry_seq for e in log.entries), timing.published, strict=True))
    as_of = {
        e.insight.insight_id: e.insight.as_of_seq
        for e in log.entries
        if isinstance(e, InsightEntry)
    }
    first = next(
        e
        for e in log.entries
        if isinstance(e, TenantItemEntry) and e.state == "on_air" and e.localized is not None
    )
    assert first.localized is not None
    expected = round(
        (stamps[first.entry_seq] - timing.played[as_of[first.localized.insight_id]]) * 1000
    )

    assert expected in finished(log).on_air


def test_explaining_is_timed_from_the_moment_to_its_insight() -> None:
    log = run()
    insights = [e for e in log.entries if isinstance(e, InsightEntry)]
    moments = [e for e in log.entries if isinstance(e, MomentEntry)]
    match = finished(log).match

    assert match.moments == len(moments)
    assert match.explain.count == len(insights)
    assert match.explain.p50_ms is not None
    assert match.explain.p50_ms > 0


def test_template_only_runs_fall_back_every_time_and_draft_nothing() -> None:
    match = finished(run()).match

    assert match.fallbacks.hit == match.fallbacks.of > 0
    assert (match.first_pass.of, match.model_drafts.of, match.model_errors) == (0, 0, 0)


def test_model_attempts_count_as_drafts_judged_errors_and_fallbacks() -> None:
    match = finished(run(with_models=True)).match
    insights = match.fallbacks.of

    assert match.fallbacks.hit == insights
    assert match.first_pass == Ratio(hit=0, of=insights)
    assert match.model_drafts == Ratio(hit=0, of=insights)
    assert match.model_errors == insights


def test_corrections_are_timed_by_the_desk() -> None:
    log = run()
    reports = [e for e in log.entries if isinstance(e, CorrectionReportEntry)]
    match = finished(log).match

    assert match.corrections.count == len(reports) > 0
    assert match.corrected_items == sum(len(r.actions) for r in reports)


def test_a_finished_run_lasts_until_its_last_entry_and_a_running_one_until_now() -> None:
    log = run()
    timing = log.timing
    last = timing.published[-1]

    assert finished(log).match.run_ms == round((last - timing.started) * 1000)
    running = measure("m42", "running", log.entries, log.timing, now=timing.started + 2.0)
    assert running.match.run_ms == 2000
    fresh = FeedLog("m42")
    idle = measure("m42", "idle", (), fresh.timing, now=fresh.now() + 2.0)
    assert idle.match.run_ms == 0


def test_the_report_gathers_every_match_against_the_objectives() -> None:
    measured = finished(run())
    targets = Targets(on_air_p50_ms=1, on_air_p95_ms=2, correction_p95_ms=10_000, within_percent=95)

    result = report([measured], generated_at=fixed_clocks().wall(), targets=targets)

    assert result.matches == (measured.match,)
    assert result.on_air.count == len(measured.on_air)
    objectives = {o.key: o for o in result.objectives}
    assert objectives["on_air_p95"].target_ms == 2
    assert objectives["on_air_p95"].measured_ms == result.on_air.p95_ms
    assert objectives["correction_p95"].measured_ms == measured.match.corrections.p95_ms
    assert result.budget.of == len(measured.on_air)
    assert result.budget.late == sum(d > 2 for d in measured.on_air)


def test_a_report_with_nothing_measured_has_no_measurements() -> None:
    result = report([], generated_at=fixed_clocks().wall(), targets=TARGETS)

    assert all(o.measured_ms is None for o in result.objectives)
    assert (result.budget.late, result.budget.of) == (0, 0)


def test_the_targets_are_the_plan_s() -> None:
    assert (
        Targets(on_air_p50_ms=4000, on_air_p95_ms=8000, correction_p95_ms=10_000, within_percent=95)
        == TARGETS
    )


@pytest.mark.parametrize("seconds", [-1.0, 7200.0])
def test_durations_stay_within_what_the_contract_allows(seconds: float) -> None:
    log = run()
    timing = log.timing
    late = measure("m42", "running", log.entries, timing, now=timing.started + seconds)

    assert 0 <= late.match.run_ms <= 3_600_000


def test_a_match_s_model_cost_prices_every_attempt_s_tokens() -> None:
    match = finished(run(with_models=True)).match
    insights = match.fallbacks.of

    assert match.tokens == TokenUse(input=5500 * insights, output=200 * insights)
    # Per insight: fast 4000 in, fallback 1500 in and 200 out, at the production prices.
    exact = insights * (4000 * 250_000 + 1500 * 400_000 + 200 * 1_600_000)
    assert match.model_cost_microusd == (exact + 500_000) // 1_000_000
    # The template partners wrote with no model: nothing to charge them.
    assert all(p.cost_microusd == 0 for p in match.partners)
    assert all(p.tokens == TokenUse(input=0, output=0) for p in match.partners)


def test_the_infrastructure_is_shared_by_the_matches_for_as_long_as_they_ran() -> None:
    log = run()
    timing = log.timing
    alone = measure("m42", "running", log.entries, timing, now=timing.started + 3600.0, costs=COSTS)
    shared = measure(
        "m42", "running", log.entries, timing, now=timing.started + 3600.0, costs=COSTS, sharing=3
    )

    assert alone.match.infra_cost_microusd == COSTS.infra_microusd_per_hour
    assert shared.match.infra_cost_microusd == round(COSTS.infra_microusd_per_hour / 3)


def test_the_report_names_the_prices_it_used() -> None:
    result = report([], generated_at=fixed_clocks().wall(), costs=COSTS)

    assert {m.model for m in result.pricing.models} == set(PRICES)
    fast = next(m for m in result.pricing.models if m.model == "fast")
    assert (fast.input_microusd_per_million, fast.output_microusd_per_million) == (
        250_000,
        2_000_000,
    )
    assert result.pricing.infra_microusd_per_hour == COSTS.infra_microusd_per_hour


def test_the_infrastructure_rate_is_the_registry_s_list_price() -> None:
    # Container Registry Basic, $0.1666 a day; everything else ran within free grants or under a
    # cent a month (docs/cost-model.md).
    assert COSTS.infra_microusd_per_hour == 6_942


def test_each_partner_is_held_to_its_own_policy_s_latency_budget() -> None:
    log = run()
    budgets: dict[TenantId, int] = {
        "northlight-sport": 1,
        "tribuna-austral": 10**6,
        "rheinblick-sport": 8000,
    }

    match = measure("m42", "finished", log.entries, log.timing, now=1e9, budgets=budgets).match

    by = {p.tenant_id: p for p in match.partners}
    for tenant_id, partner in by.items():
        assert partner.latency_budget_ms == budgets[tenant_id]
        assert partner.within_budget.of == partner.on_air.count
    assert by["northlight-sport"].within_budget.hit == 0
    assert by["tribuna-austral"].within_budget.hit == by["tribuna-austral"].on_air.count


def test_a_partner_without_a_known_budget_is_judged_against_none() -> None:
    match = finished(run()).match

    assert all(p.latency_budget_ms is None for p in match.partners)
    assert all(p.within_budget == Ratio(hit=0, of=0) for p in match.partners)
