"""The Proving Ground's scorecard and the Release Gate's verdict, as they travel."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import parse_gate_verdict, parse_scorecard


def ratio(hit: int, of: int) -> dict[str, int]:
    return {"hit": hit, "of": of}


def scorecard(**changes: object) -> dict[str, Any]:
    card: dict[str, Any] = {
        "configuration": {
            "name": "production",
            "analystPrompt": "analyst/v1.2",
            "localizerPrompt": "localizer/v1.0",
            "models": ["fast", "fallback"],
        },
        "matches": 20,
        "firstMatch": "m1001",
        "generatedAt": "2026-10-12T01:00:00.000Z",
        "metrics": {
            "supportedClaims": ratio(118, 120),
            "storylineRecall": ratio(45, 50),
            "keyMomentPrecision": ratio(60, 64),
            "verifierCatch": ratio(80, 80),
            "policyViolations": 0,
            "modelWritten": ratio(58, 64),
            "firstAttemptPass": ratio(50, 58),
            "correctionsCarried": ratio(12, 12),
            "latencyMs": {"p50": 1800.0, "p95": 4100.0},
            "costUsd": 0.42,
        },
        "failures": [
            {
                "matchId": "m1003",
                "itemId": "it-northlight-sport-in-m1003-goal-HCY-s0287-a1-v1",
                "claimId": "cl-1",
                "text": "{{player:HCY-19}} scores",
                "eventIds": ["m1003-e0287"],
                "reasons": ["names HCY-19, who is not credited in its events"],
            }
        ],
    }
    card.update(changes)
    return card


def test_a_scorecard_reads_back_as_it_was_written() -> None:
    card = parse_scorecard(scorecard())

    assert card.metrics.storyline_recall.hit == 45
    assert parse_scorecard(card.to_wire()) == card


def test_a_ratio_never_counts_more_hits_than_cases() -> None:
    metrics = scorecard()["metrics"] | {"storylineRecall": ratio(51, 50)}

    with pytest.raises(ValidationError):
        parse_scorecard(scorecard(metrics=metrics))


def test_a_run_without_a_model_has_no_latency_or_cost_to_report() -> None:
    metrics = scorecard()["metrics"] | {"latencyMs": None, "costUsd": None}

    assert parse_scorecard(scorecard(metrics=metrics)).metrics.cost_usd is None


@pytest.mark.parametrize(
    "change",
    [
        {"matches": 0},
        {"matches": 101},
        {"firstMatch": "b1001"},
        {"configuration": scorecard()["configuration"] | {"name": "Prod uction"}},
        {"configuration": scorecard()["configuration"] | {"analystPrompt": "../etc/passwd"}},
    ],
)
def test_a_malformed_scorecard_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        parse_scorecard(scorecard(**change))


def test_a_verdict_lists_every_rule_and_blocks_when_any_fails() -> None:
    verdict = parse_gate_verdict(
        {
            "candidate": "candidate",
            "baseline": "production",
            "allowed": False,
            "checks": [
                {"rule": "unsupported_claims", "passed": False, "detail": "2 unsupported"},
                {"rule": "storyline_recall", "passed": True, "detail": "90.0% (was 88.0%)"},
            ],
        }
    )

    assert not verdict.allowed


def test_a_verdict_that_allows_a_failing_rule_is_refused() -> None:
    with pytest.raises(ValidationError):
        parse_gate_verdict(
            {
                "candidate": "candidate",
                "baseline": "production",
                "allowed": True,
                "checks": [{"rule": "policy_violations", "passed": False, "detail": "1"}],
            }
        )
