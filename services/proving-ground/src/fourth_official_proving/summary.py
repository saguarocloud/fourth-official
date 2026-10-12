"""The Release Gate's job summary in Markdown: counts and the gate's own words only.

Claim text is written by a model and may come from a pull request's prompt, so it is never
repeated here; the scorecard artifact holds it for anyone who needs to read it.
"""

from fourth_official_contracts import GateVerdict, Ratio, Scorecard

PERCENT = 100


def _ratio(ratio: Ratio) -> str:
    rate = f" ({ratio.hit / ratio.of * PERCENT:.1f}%)" if ratio.of else ""
    return f"{ratio.hit} of {ratio.of}{rate}"


def _measures(card: Scorecard) -> list[str]:
    m = card.metrics
    rows = [
        ("Supported claims", _ratio(m.supported_claims)),
        ("Storyline recall", _ratio(m.storyline_recall)),
        ("Key-moment precision", _ratio(m.key_moment_precision)),
        ("Verifier catch", _ratio(m.verifier_catch)),
        ("Corrections carried", _ratio(m.corrections_carried)),
        ("Policy violations", str(m.policy_violations)),
        ("Model written", _ratio(m.model_written)),
        ("First-attempt pass", _ratio(m.first_attempt_pass)),
        (
            "Latency",
            f"p50 {m.latency_ms.p50:,.0f} ms · p95 {m.latency_ms.p95:,.0f} ms"
            if m.latency_ms
            else "not measured",
        ),
        ("Cost", f"${m.cost_usd:.4f}" if m.cost_usd is not None else "none"),
    ]
    return ["| Measure | Result |", "|---|---|", *(f"| {k} | {v} |" for k, v in rows)]


def render(card: Scorecard | None, verdict: GateVerdict | None, *, has_baseline: bool) -> str:
    if card is None:
        return "## Proving Ground\n\nNo scorecard was produced; see the job log.\n"
    name = card.configuration.name
    if verdict is None and has_baseline:
        title = f"## Release Gate: the gate could not judge {name}; see the job log"
    elif verdict is None:
        title = (
            f"## Proving Ground: {name} "
            "(not gated: the base branch has no production configuration yet)"
        )
    else:
        title = f"## Release Gate: {name} is {'allowed' if verdict.allowed else 'blocked'}"
    lines = [
        title,
        "",
        f"{card.matches} benchmark matches from {card.first_match}, "
        f"Analyst prompt `{card.configuration.analyst_prompt}`.",
        "",
        *_measures(card),
    ]
    if card.failures:
        count = len(card.failures)
        noun = "claim" if count == 1 else "claims"
        lines += ["", f"{count} failed {noun} listed in the scorecard artifact."]
    if verdict is not None:
        lines += ["", "| Result | Rule | Detail |", "|---|---|---|"]
        lines += [
            f"| {'pass' if c.passed else '**block**'} | {c.rule} | {c.detail} |"
            for c in verdict.checks
        ]
    return "\n".join(lines) + "\n"
