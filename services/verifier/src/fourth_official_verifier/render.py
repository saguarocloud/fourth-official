"""Turn claim markup into text. Code renders every number and name; a model never does."""

import re
from collections.abc import Collection

from fourth_official_contracts import Insight, claim_references
from fourth_official_verifier.facts import MatchFacts

_TOKEN = re.compile(r"\{\{([^{}]*)\}\}")
PERCENT_METRICS = frozenset({"possession", "field_tilt", "pass_completion"})
COUNT_METRICS = frozenset({"passes", "shots", "shots_on_target"})
ONE_DECIMAL_METRICS = frozenset({"ppda"})
WHOLE_METRICS = frozenset({"control_chaos"})
# Scores are written with an en dash, as broadcasters do.
EN_DASH = "\u2013"


class RenderError(ValueError):
    """A reference that cannot be rendered: verify the insight first."""


def format_value(metric: str, value: float) -> str:
    """A metric value as a viewer reads it."""
    if metric in PERCENT_METRICS:
        return f"{round(value * 100)}%"
    if metric in COUNT_METRICS or metric in WHOLE_METRICS:
        return f"{round(value)}"
    if metric in ONE_DECIMAL_METRICS:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _value(argument: str, facts: MatchFacts, as_of_seq: int, cited: Collection[str]) -> str:
    snapshot = facts.snapshots.get(argument)
    if argument not in cited or snapshot is None:
        raise RenderError("a value must be a cited, known snapshot")
    if snapshot.as_of_seq > as_of_seq:
        raise RenderError("a value cannot come from after the moment")
    if snapshot.value is None:
        raise RenderError("a snapshot without a value cannot be rendered")
    return format_value(snapshot.metric, snapshot.value)


def _render_token(token: str, facts: MatchFacts, as_of_seq: int, cited: Collection[str]) -> str:
    kind, _, argument = token.partition(":")
    if kind == "minute":
        return f"{int(argument)}'"
    if kind == "score":
        home, away = facts.score_at(as_of_seq)
        return f"{home}{EN_DASH}{away}"
    if kind == "value":
        return _value(argument, facts, as_of_seq, cited)
    names = facts.player_names if kind == "player" else facts.club_names
    if argument not in names:
        raise RenderError(f"no {kind} with that ID in this match")
    return names[argument]


def render(text: str, facts: MatchFacts, *, as_of_seq: int, cited: Collection[str]) -> str:
    """Render claim text at a moment, with only the snapshots it cites. Raises `RenderError` if
    anything does not resolve: render only what the Verifier passed."""
    claim_references(text)  # refuses malformed markup before anything is substituted
    return _TOKEN.sub(lambda found: _render_token(found.group(1), facts, as_of_seq, cited), text)


def render_insight(insight: Insight, facts: MatchFacts) -> tuple[str, tuple[str, ...]]:
    """The headline and every claim, rendered at the insight's moment from their own evidence."""
    every = {s for c in insight.claims for s in c.evidence.metric_snapshot_ids}
    headline = render(insight.headline, facts, as_of_seq=insight.as_of_seq, cited=every)
    claims = tuple(
        render(c.text, facts, as_of_seq=insight.as_of_seq, cited=c.evidence.metric_snapshot_ids)
        for c in insight.claims
    )
    return headline, claims
