"""Deterministic verification of insights, the code that renders their facts, and the template
insights used when nothing else passes."""

from fourth_official_verifier.facts import MatchFacts
from fourth_official_verifier.render import format_value, render
from fourth_official_verifier.templates import template_insight
from fourth_official_verifier.verify import verify

__all__ = ["MatchFacts", "format_value", "render", "template_insight", "verify"]
