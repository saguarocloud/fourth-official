"""Measures over runs of the real pipeline: template-written, so deterministic and free."""

import asyncio
from dataclasses import replace
from functools import cache

from fourth_official_contracts import CorrectionReportEntry, TenantItemEntry
from fourth_official_explain import Explanation, explain
from fourth_official_proving.metrics import (
    corrections_carried,
    first_attempt_pass,
    key_moment_precision,
    latency,
    model_written,
    policy_violations,
    storyline_recall,
    supported_claims,
)
from fourth_official_proving.runner import MatchRun, run_benchmark
from fourth_official_simulator.benchmark import benchmark_matches
from fourth_official_simulator.demo import demo_matchday


async def template(moment: object, facts: object) -> Explanation:
    return await explain(moment, facts, [])  # type: ignore[arg-type]


@cache
def demo() -> tuple[MatchRun, ...]:
    return asyncio.run(run_benchmark(demo_matchday(), template))


@cache
def bench() -> tuple[MatchRun, ...]:
    return asyncio.run(run_benchmark(benchmark_matches(12), template))


def without_the_desk(run: MatchRun) -> MatchRun:
    """The run as if no correction had reached any partner item."""
    kept = tuple(
        e
        for e in run.entries
        if not isinstance(e, CorrectionReportEntry)
        and not (
            isinstance(e, TenantItemEntry)
            and (e.state in ("retracted", "amended") or e.overlay.supersedes is not None)
        )
    )
    return replace(run, entries=kept)


def test_everything_on_air_at_full_time_is_true_when_corrections_are_carried() -> None:
    ratio, failures = supported_claims(demo())

    assert ratio.of > 0
    assert ratio.hit == ratio.of
    assert failures == ()


def test_claims_left_on_air_after_a_correction_are_caught() -> None:
    ratio, failures = supported_claims([without_the_desk(r) for r in demo()])

    assert ratio.hit < ratio.of
    reasons = {reason for f in failures for reason in f.reasons}
    assert "rests on m42-e1702, which was ruled out" in reasons
    assert any("who is not credited in its events" in r for r in reasons)


def test_a_remade_item_is_held_to_its_own_words() -> None:
    _, failures = supported_claims(demo())

    assert not any(f.item_id.endswith("-v2") for f in failures)


def test_corrections_are_carried_to_every_item_resting_on_them() -> None:
    carried = corrections_carried(demo())

    assert carried.of > 0
    assert carried.hit == carried.of
    undone = corrections_carried([without_the_desk(r) for r in demo()])
    assert undone.hit < undone.of


def test_the_pipeline_surfaces_the_storylines_planted_in_the_benchmark() -> None:
    recall = storyline_recall(bench())

    assert recall.of >= 20
    assert recall.hit / recall.of >= 0.85


def test_published_insights_are_about_key_moments() -> None:
    precision = key_moment_precision(bench())

    assert precision.of > 0
    assert precision.hit / precision.of >= 0.8


def test_no_partner_airs_what_its_policy_forbids() -> None:
    assert policy_violations(bench()) == 0


def test_a_template_run_has_no_model_writing_and_no_latency_to_report() -> None:
    written = model_written(demo())

    assert written.hit == 0
    assert written.of > 0
    assert first_attempt_pass(demo()).of == 0
    assert latency(demo()) is None


def tampered(run: MatchRun, template: str, **overlay: object) -> MatchRun:
    """The run with the last on-air item of this template aired differently."""
    entries = list(run.entries)
    index = max(
        i
        for i, e in enumerate(entries)
        if isinstance(e, TenantItemEntry)
        and e.state == "on_air"
        and e.overlay.content.template == template
    )
    item = entries[index]
    assert isinstance(item, TenantItemEntry)
    entries[index] = item.model_copy(update={"overlay": item.overlay.model_copy(update=overlay)})
    return replace(run, entries=tuple(entries))


def test_a_narrative_item_aired_without_its_disclosure_breaks_policy() -> None:
    (m42, *rest) = demo()

    assert policy_violations([tampered(m42, "lower_third", disclosure=None), *rest]) == 1


def test_a_score_bug_is_held_to_its_partners_policy_too() -> None:
    (m42, *rest) = demo()
    labelled = next(
        e.overlay.disclosure
        for e in m42.entries
        if isinstance(e, TenantItemEntry) and e.overlay.disclosure is not None
    )

    assert policy_violations([tampered(m42, "score_bug", disclosure=labelled), *rest]) == 1
