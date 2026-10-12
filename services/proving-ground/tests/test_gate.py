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
        "storyline_recall",
        "model_written",
        "latency_p95",
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


def test_falling_back_to_the_template_much_more_often_blocks() -> None:
    verdict = gate(card("candidate", modelWritten={"hit": 50, "of": 64}), BASELINE)

    assert [c.rule for c in verdict.checks if not c.passed] == ["model_written"]


def test_p95_latency_may_grow_fifteen_percent_and_no_more() -> None:
    within = card("candidate", latencyMs={"p50": 1900.0, "p95": 4600.0})
    beyond = card("candidate", latencyMs={"p50": 1900.0, "p95": 4601.0})

    assert gate(within, BASELINE).allowed
    assert not gate(beyond, BASELINE).allowed


def test_latency_is_not_compared_when_either_run_wrote_without_a_model() -> None:
    template = card("template", latencyMs=None, modelWritten={"hit": 0, "of": 64})
    verdict = gate(
        template, card("template-baseline", latencyMs=None, modelWritten={"hit": 0, "of": 64})
    )

    latency = next(c for c in verdict.checks if c.rule == "latency_p95")
    assert latency.passed
    assert latency.detail == "not measured: no model wrote in one of the runs"


def test_runs_over_different_benchmarks_cannot_be_compared() -> None:
    other = parse_scorecard(card("candidate").to_wire() | {"matches": 100})

    with pytest.raises(ValueError, match="same benchmark"):
        gate(other, BASELINE)
