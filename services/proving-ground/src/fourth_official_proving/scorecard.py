"""A run's scorecard: every measure as counts, and the failed claims to drill into."""

from collections.abc import Sequence
from datetime import datetime

from fourth_official_contracts import Configuration, Metrics, Scorecard
from fourth_official_contracts.scorecard import MAX_FAILURES
from fourth_official_proving.adversarial import verifier_catch
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
from fourth_official_proving.runner import MatchRun


def score(
    configuration: Configuration,
    runs: Sequence[MatchRun],
    *,
    generated_at: datetime,
    cost_usd: float | None = None,
) -> Scorecard:
    """The scorecard for one configuration's runs over the start of the benchmark."""
    if not runs:
        raise ValueError("a scorecard needs at least one match")
    supported, failures = supported_claims(runs)
    return Scorecard(
        configuration=configuration,
        matches=len(runs),
        first_match=runs[0].setup.match_id,
        generated_at=generated_at,
        metrics=Metrics(
            supported_claims=supported,
            storyline_recall=storyline_recall(runs),
            key_moment_precision=key_moment_precision(runs),
            verifier_catch=verifier_catch(runs),
            policy_violations=policy_violations(runs),
            model_written=model_written(runs),
            first_attempt_pass=first_attempt_pass(runs),
            corrections_carried=corrections_carried(runs),
            latency_ms=latency(runs),
            cost_usd=cost_usd,
        ),
        failures=failures[:MAX_FAILURES],
    )
