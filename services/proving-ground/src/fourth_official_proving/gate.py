"""The Release Gate (plan §9.3): a candidate configuration is allowed only if, over the same
benchmark as the production baseline, nothing on air is untrue, no partner's policy is broken,
the Verifier refuses every planted lie, every correction reaches what rests on it, and it is not
materially worse at finding stories, writing them, or answering in time.

Rates are compared exactly, as integer cross-products of their counts; rounding is for display.
"""

from fourth_official_contracts import GateCheck, GateRule, GateVerdict, Ratio, Scorecard

# Points of storyline recall a candidate may lose (plan §9.3).
RECALL_POINTS = 3
# Points of model-written insights a candidate may lose: more falls back to the template.
MODEL_WRITTEN_POINTS = 5
# How much slower, at the 95th percentile, a candidate may explain a moment (plan §9.3)...
LATENCY_GROWTH = 0.15
# ...and by at least this much: p95 over a smoke run's ~80 moments is its slowest four model
# calls, which vary by seconds between identical runs (CI measured 11.3 s, then 13.7 s).
LATENCY_NOISE_MS = 5000.0
PERCENT = 100


def _rate(ratio: Ratio) -> float:
    return ratio.hit / ratio.of if ratio.of else 1.0


def _percent(ratio: Ratio) -> str:
    return f"{_rate(ratio) * PERCENT:.1f}%"


def _unsupported(candidate: Scorecard, baseline: Scorecard) -> GateCheck:
    claims = candidate.metrics.supported_claims
    unsupported = claims.of - claims.hit
    # A candidate that put nothing on air proves nothing, where the baseline did.
    silent = claims.of == 0 < baseline.metrics.supported_claims.of
    return GateCheck(
        rule="unsupported_claims",
        passed=unsupported == 0 and not silent,
        detail=f"{unsupported} of {claims.of} claims on air at full time are unsupported",
    )


def _all(rule: GateRule, ratio: Ratio, measure: str) -> GateCheck:
    return GateCheck(
        rule=rule, passed=ratio.hit == ratio.of, detail=f"{ratio.hit} of {ratio.of} {measure}"
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
    # candidate.hit / candidate.of >= baseline.hit / baseline.of - points / 100, in integers.
    if candidate.of == 0:
        passed = baseline.of == 0
    elif baseline.of == 0:
        passed = True
    else:
        passed = (
            candidate.hit * baseline.of * PERCENT
            >= (baseline.hit * PERCENT - points * baseline.of) * candidate.of
        )
    return GateCheck(
        rule=rule,
        passed=passed,
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
        passed=ours.p95 <= max(theirs.p95 * (1 + LATENCY_GROWTH), theirs.p95 + LATENCY_NOISE_MS),
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
        _unsupported(candidate, baseline),
        _policy(candidate),
        _all("verifier_catch", candidate.metrics.verifier_catch, "planted lies refused"),
        _all(
            "corrections_carried",
            candidate.metrics.corrections_carried,
            "items resting on a correction pulled or replaced",
        ),
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
