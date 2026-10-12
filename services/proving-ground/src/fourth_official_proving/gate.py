"""The Release Gate (plan §9.3): a candidate configuration is allowed only if, over the same
benchmark as the production baseline, nothing on air is untrue, no partner's policy is broken, and
it is not materially worse at finding stories, writing them, or answering in time.
"""

from fourth_official_contracts import GateCheck, GateRule, GateVerdict, Ratio, Scorecard

# Points of storyline recall a candidate may lose (plan §9.3).
RECALL_POINTS = 3
# Points of model-written insights a candidate may lose: more falls back to the template.
MODEL_WRITTEN_POINTS = 5
# How much slower, at the 95th percentile, a candidate may explain a moment (plan §9.3).
LATENCY_GROWTH = 0.15
PERCENT = 100


def _rate(ratio: Ratio) -> float:
    return ratio.hit / ratio.of if ratio.of else 1.0


def _percent(ratio: Ratio) -> str:
    return f"{_rate(ratio) * PERCENT:.1f}%"


def _unsupported(candidate: Scorecard) -> GateCheck:
    claims = candidate.metrics.supported_claims
    unsupported = claims.of - claims.hit
    return GateCheck(
        rule="unsupported_claims",
        passed=unsupported == 0,
        detail=f"{unsupported} of {claims.of} claims on air at full time are unsupported",
    )


def _policy(candidate: Scorecard) -> GateCheck:
    violations = candidate.metrics.policy_violations
    return GateCheck(
        rule="policy_violations",
        passed=violations == 0,
        detail=f"{violations} partner items on air break their partner's policy",
    )


def _no_worse(
    rule: GateRule,
    *,
    measure: str,
    candidate: Ratio,
    baseline: Ratio,
    points: int,
    name: str,
) -> GateCheck:
    allowed = _rate(baseline) - points / PERCENT
    return GateCheck(
        rule=rule,
        # Rounded to the percentage shown, so the verdict and its detail always agree.
        passed=round(_rate(candidate) * PERCENT, 1) >= round(allowed * PERCENT, 1),
        detail=f"{_percent(candidate)} {measure} ({name}: {_percent(baseline)})",
    )


def _latency(candidate: Scorecard, baseline: Scorecard) -> GateCheck:
    ours, theirs = candidate.metrics.latency_ms, baseline.metrics.latency_ms
    if ours is None or theirs is None:
        return GateCheck(
            rule="latency_p95",
            passed=True,
            detail="not measured: no model wrote in one of the runs",
        )
    return GateCheck(
        rule="latency_p95",
        passed=ours.p95 <= theirs.p95 * (1 + LATENCY_GROWTH),
        detail=(
            f"p95 {ours.p95:.0f} ms to explain a moment "
            f"({baseline.configuration.name}: {theirs.p95:.0f} ms)"
        ),
    )


def gate(candidate: Scorecard, baseline: Scorecard) -> GateVerdict:
    """The verdict for `candidate` against `baseline`; both must cover the same benchmark."""
    same = (candidate.matches, candidate.first_match) == (baseline.matches, baseline.first_match)
    if not same:
        raise ValueError("a candidate is compared only over the same benchmark as its baseline")
    name = baseline.configuration.name
    checks = (
        _unsupported(candidate),
        _policy(candidate),
        _no_worse(
            "storyline_recall",
            measure="of planted storylines surfaced",
            candidate=candidate.metrics.storyline_recall,
            baseline=baseline.metrics.storyline_recall,
            points=RECALL_POINTS,
            name=name,
        ),
        _no_worse(
            "model_written",
            measure="of insights written by a model",
            candidate=candidate.metrics.model_written,
            baseline=baseline.metrics.model_written,
            points=MODEL_WRITTEN_POINTS,
            name=name,
        ),
        _latency(candidate, baseline),
    )
    return GateVerdict(
        candidate=candidate.configuration.name,
        baseline=name,
        allowed=all(c.passed for c in checks),
        checks=checks,
    )
