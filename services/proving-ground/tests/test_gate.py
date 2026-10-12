"""The Release Gate: a candidate configuration ships only if it is no worse where it matters."""

from typing import Any

import pytest

from fourth_official_contracts import Scorecard, parse_scorecard
from fourth_official_proving.gate import gate


def card(name: str, **metrics: object) -> Scorecard:
    base: dict[str, Any] = {
        "supportedClaims": {"hit": 120, "of": 120},
        "storylineRecall": {"hit": 45, "of": 50},
        "keyMomentPrecision": {"hit": 60, "of": 64},
        "verifierCatch": {"hit": 80, "of": 80},
        "policyViolations": 0,
        "modelWritten": {"hit": 58, "of": 64},
        "firstAttemptPass": {"hit": 50, "of": 58},
        "correctionsCarried": {"hit": 12, "of": 12},
        "latencyMs": {"p50": 1800.0, "p95": 4000.0},
        "costUsd": 0.4,
    }
    return parse_scorecard(
        {
            "configuration": {
                "name": name,
                "analystPrompt": "analyst/v1.2",
                "localizerPrompt": "localizer/v1.0",
                "models": ["fast"],
            },
            "matches": 20,
            "firstMatch": "m1001",
            "generatedAt": "2026-10-12T01:00:00.000Z",
            "metrics": base | metrics,
            "failures": [],
        }
    )


BASELINE = card("production")


def test_a_candidate_no_worse_anywhere_is_allowed() -> None:
    verdict = gate(card("candidate"), BASELINE)

    assert verdict.allowed
    assert [c.rule for c in verdict.checks] == [
        "unsupported_claims",
        "policy_violations",
        "verifier_catch",
        "corrections_carried",
        "storyline_recall",
        "model_written",
        "latency_p50",
    ]


def test_a_single_unsupported_claim_on_air_blocks() -> None:
    verdict = gate(card("candidate", supportedClaims={"hit": 118, "of": 120}), BASELINE)

    assert not verdict.allowed
    (check,) = [c for c in verdict.checks if not c.passed]
    assert check.rule == "unsupported_claims"
    assert check.detail == "2 of 120 claims on air at full time are unsupported"


def test_a_policy_violation_blocks() -> None:
    assert not gate(card("candidate", policyViolations=1), BASELINE).allowed


def test_recall_may_dip_three_points_and_no_more() -> None:
    dipped = gate(card("candidate", storylineRecall={"hit": 44, "of": 50}), BASELINE)
    dropped = gate(card("candidate", storylineRecall={"hit": 43, "of": 50}), BASELINE)

    assert dipped.allowed
    assert not dropped.allowed
    (check,) = [c for c in dropped.checks if not c.passed]
    assert check.detail == "86.0% of planted storylines surfaced (production: 90.0%)"


def test_recall_is_compared_exactly_not_after_rounding() -> None:
    # 90% then 86.96%: 3.04 points lost, which rounds to 3.0 but is more than 3.
    lost = gate(card("candidate", storylineRecall={"hit": 4348, "of": 5000}), BASELINE)
    kept = gate(card("candidate", storylineRecall={"hit": 4350, "of": 5000}), BASELINE)

    assert not lost.allowed
    assert kept.allowed


def test_a_candidate_that_published_nothing_is_blocked() -> None:
    silent = card(
        "candidate",
        supportedClaims={"hit": 0, "of": 0},
        modelWritten={"hit": 0, "of": 0},
        firstAttemptPass={"hit": 0, "of": 0},
    )
    failed = [c.rule for c in gate(silent, BASELINE).checks if not c.passed]

    assert failed == ["unsupported_claims", "model_written"]


def test_a_lie_the_verifier_lets_through_blocks() -> None:
    verdict = gate(card("candidate", verifierCatch={"hit": 79, "of": 80}), BASELINE)

    (check,) = [c for c in verdict.checks if not c.passed]
    assert check.detail == "79 of 80 planted lies refused"


def test_a_correction_left_unpulled_blocks() -> None:
    verdict = gate(card("candidate", correctionsCarried={"hit": 11, "of": 12}), BASELINE)

    assert [c.rule for c in verdict.checks if not c.passed] == ["corrections_carried"]


def test_falling_back_to_the_template_much_more_often_blocks() -> None:
    verdict = gate(card("candidate", modelWritten={"hit": 50, "of": 64}), BASELINE)

    assert [c.rule for c in verdict.checks if not c.passed] == ["model_written"]


def p50(ms: float) -> Scorecard:
    return card("candidate", latencyMs={"p50": ms, "p95": 60000.0})


def test_the_median_time_may_grow_fifteen_percent_and_no_more() -> None:
    slow = card("production", latencyMs={"p50": 20000.0, "p95": 40000.0})

    assert gate(p50(23000.0), slow).allowed
    assert not gate(p50(23001.0), slow).allowed


def test_a_couple_of_seconds_of_noise_never_blocks() -> None:
    assert gate(p50(3800.0), BASELINE).allowed
    assert not gate(p50(3801.0), BASELINE).allowed


def test_the_tail_is_reported_not_ruled_on() -> None:
    # p95 over a smoke run's ~80 moments is whether a few drafts needed a retry: identical code
    # in CI measured 13.1 s and 20.1 s. The median is the rule; the tail is in the scorecard.
    assert gate(card("candidate", latencyMs={"p50": 1800.0, "p95": 400000.0}), BASELINE).allowed


def test_latency_is_not_compared_when_either_run_wrote_without_a_model() -> None:
    template = card("template", latencyMs=None, modelWritten={"hit": 0, "of": 64})
    verdict = gate(
        template, card("template-baseline", latencyMs=None, modelWritten={"hit": 0, "of": 64})
    )

    latency = next(c for c in verdict.checks if c.rule == "latency_p50")
    assert latency.passed
    assert latency.detail == "not measured: no model wrote in one of the runs"


def test_runs_over_different_benchmarks_cannot_be_compared() -> None:
    other = parse_scorecard(card("candidate").to_wire() | {"matches": 100})

    with pytest.raises(ValueError, match="same benchmark"):
        gate(other, BASELINE)
