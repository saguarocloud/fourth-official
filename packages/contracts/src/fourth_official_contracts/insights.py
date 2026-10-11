"""Insights: an explanation of a moment as typed claims, each with its evidence (stage three).

Claims never contain raw numbers or names. They reference facts with markup, and code renders
those facts from the evidence, so a model never states a number it calculated:

- `{{value:<snapshotId>}}`: a metric value, formatted by code
- `{{player:<playerId>}}` and `{{club:<clubCode>}}`: a name from the squad lists
- `{{minute:<n>}}`: a match minute
- `{{score}}`: the score at the moment

The contract checks the shape (markup is well-formed, every value cited, evidence present); the
Verifier checks the truth against the match.
"""

import re
import unicodedata
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.metrics import SnapshotId
from fourth_official_contracts.moments import MomentId
from fourth_official_contracts.primitives import EventId, MatchId, Seq, WireModel, match_of

ClaimType = Literal["stat", "comparison", "causal", "milestone"]
ReferenceKind = Literal["player", "club", "value", "minute", "score"]
MAX_CLAIMS = 5
MAX_MINUTE = 130

_TOKEN = re.compile(r"\{\{([^{}]*)\}\}")
_ARGUMENT = {
    "player": re.compile(r"^[A-Z]{3}-[0-9]{2}$"),
    "club": re.compile(r"^[A-Z]{3}$"),
    "value": re.compile(
        r"^ms-m[0-9]{1,12}-[a-z_]{2,24}-([A-Z]{3}|match)-(5m|15m|match)-s[0-9]{4,9}-v[0-9]{1,4}$"
    ),
    "minute": re.compile(r"^(0|[1-9][0-9]{0,2})$"),
}


def claim_references(text: str) -> tuple[tuple[ReferenceKind, str], ...]:
    """The facts a piece of claim text references, in order. Raises on malformed markup."""
    references: list[tuple[ReferenceKind, str]] = []
    for token in _TOKEN.findall(text):
        kind, _, argument = token.partition(":")
        if kind == "score" and not argument:
            references.append(("score", ""))
            continue
        pattern = _ARGUMENT.get(kind)
        if pattern is None or not pattern.match(argument):
            raise ValueError("malformed markup: references are {{kind:argument}} with a known kind")
        if kind == "minute" and int(argument) > MAX_MINUTE:
            raise ValueError(f"malformed markup: minute {argument} is beyond the match")
        references.append((kind, argument))
    if "{{" in _TOKEN.sub("", text) or "}}" in _TOKEN.sub("", text):
        raise ValueError("malformed markup: unbalanced braces")
    return tuple(references)


ClaimText = Annotated[str, StringConstraints(min_length=1, max_length=280)]
HeadlineText = Annotated[str, StringConstraints(min_length=1, max_length=120)]


# Control, format (bidirectional overrides, zero-width), separator and private-use characters.
_REFUSED_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


def _single_line(text: str) -> None:
    if any(unicodedata.category(c) in _REFUSED_CATEGORIES for c in text):
        raise ValueError("claim text must be a single line of printable characters")


class Evidence(WireModel):
    event_ids: Annotated[tuple[EventId, ...], Field(max_length=64, strict=False)]
    metric_snapshot_ids: Annotated[tuple[SnapshotId, ...], Field(max_length=16, strict=False)]


class Claim(WireModel):
    claim_id: Annotated[str, StringConstraints(pattern=r"^cl-[0-9]{1,3}$")]
    type: ClaimType
    text: ClaimText
    evidence: Evidence

    @model_validator(mode="after")
    def _text_is_backed_by_evidence(self) -> "Claim":
        _single_line(self.text)
        if not (self.evidence.event_ids or self.evidence.metric_snapshot_ids):
            raise ValueError("a claim needs at least one piece of evidence")
        cited = set(self.evidence.metric_snapshot_ids)
        for kind, argument in claim_references(self.text):
            if kind == "value" and argument not in cited:
                raise ValueError(f"value {argument} is not cited in the claim's evidence")
        return self


class Provenance(WireModel):
    """Who produced the insight and how: recorded for every published item."""

    agent: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z-]{1,31}$")]
    prompt_version: Annotated[str, StringConstraints(pattern=r"^v[0-9]{1,3}\.[0-9]{1,3}$")]
    # The deployment alias from configuration (for example `fast`), never a hard-coded model.
    model: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9.-]{0,63}$")]
    produced_by: Literal["model", "template"]


def insight_id_for(moment_id: str, *, attempt: int) -> str:
    """An insight is named after its moment and the attempt that produced it."""
    return f"in-{moment_id.removeprefix('mo-')}-a{attempt}"


class Insight(WireModel):
    insight_id: Annotated[
        str,
        StringConstraints(
            max_length=72,
            pattern=r"^in-m[0-9]{1,12}-[a-z_]{2,24}-[A-Z]{3}-s[0-9]{4,9}-a[0-9]{1,2}$",
        ),
    ]
    match_id: MatchId
    moment_id: MomentId
    as_of_seq: Seq
    # Insights are written once in the canonical language, verified, and only then localised.
    locale: Literal["en"]
    headline: HeadlineText
    claims: Annotated[tuple[Claim, ...], Field(min_length=1, max_length=MAX_CLAIMS, strict=False)]
    provenance: Provenance

    @model_validator(mode="after")
    def _identity_and_claims_are_consistent(self) -> "Insight":
        attempt = self.insight_id.rsplit("-a", 1)[1]
        if self.insight_id != insight_id_for(self.moment_id, attempt=int(attempt)):
            raise ValueError(f"insight id {self.insight_id} does not name moment {self.moment_id}")
        if not self.moment_id.startswith(f"mo-{self.match_id}-"):
            raise ValueError(f"moment {self.moment_id} belongs to another match")
        ids = [c.claim_id for c in self.claims]
        if len(set(ids)) != len(ids):
            raise ValueError("claim ids must be unique")
        for item in self.claims:
            if any(match_of(e) != self.match_id for e in item.evidence.event_ids):
                raise ValueError(f"claim {item.claim_id} cites an event from another match")
        _single_line(self.headline)
        cited = {s for c in self.claims for s in c.evidence.metric_snapshot_ids}
        for kind, argument in claim_references(self.headline):
            if kind == "value" and argument not in cited:
                raise ValueError(f"headline value {argument} is not cited by any claim")
        return self


# The model's own config already hides input in validation errors.
INSIGHT_ADAPTER: TypeAdapter[Insight] = TypeAdapter(Insight)


def parse_insight(raw: object) -> Insight:
    """Validate decoded wire data (camelCase keys only) into an insight."""
    return INSIGHT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)


def parse_insight_json(data: str | bytes) -> Insight:
    """Validate JSON text into an insight."""
    return INSIGHT_ADAPTER.validate_json(data, by_alias=True, by_name=False)
