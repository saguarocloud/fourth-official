"""Turn claim markup into text. Code renders every number and name; a model never does."""

import re

from fourth_official_contracts import claim_references
from fourth_official_verifier.facts import MatchFacts

_TOKEN = re.compile(r"\{\{([^{}]*)\}\}")
PERCENT_METRICS = frozenset({"possession", "field_tilt", "pass_completion"})
COUNT_METRICS = frozenset({"passes", "shots", "shots_on_target"})
ONE_DECIMAL_METRICS = frozenset({"ppda"})
WHOLE_METRICS = frozenset({"control_chaos"})
# Scores are written with an en dash, as broadcasters do.
EN_DASH = "\u2013"


def format_value(metric: str, value: float) -> str:
    """A metric value as a viewer reads it."""
    if metric in PERCENT_METRICS:
        return f"{round(value * 100)}%"
    if metric in COUNT_METRICS or metric in WHOLE_METRICS:
        return f"{round(value)}"
    if metric in ONE_DECIMAL_METRICS:
        return f"{value:.1f}"
    return f"{value:.2f}"


def _render_token(token: str, facts: MatchFacts, as_of_seq: int) -> str:
    kind, _, argument = token.partition(":")
    if kind == "player":
        return facts.player_names[argument]
    if kind == "club":
        return facts.club_names[argument]
    if kind == "minute":
        return f"{int(argument)}'"
    if kind == "score":
        home, away = facts.score_at(as_of_seq)
        return f"{home}{EN_DASH}{away}"
    snapshot = facts.snapshots[argument]
    if snapshot.value is None:
        raise ValueError(f"snapshot {argument} has no value to render")
    return format_value(snapshot.metric, snapshot.value)


def render(text: str, facts: MatchFacts, *, as_of_seq: int) -> str:
    """Render verified claim text. Raises if a reference does not resolve: verify first."""
    claim_references(text)  # refuses malformed markup before anything is substituted
    return _TOKEN.sub(lambda found: _render_token(found.group(1), facts, as_of_seq), text)
