"""Tenants: the broadcast partners, each with its own editorial policy (stage five, personalise).

A policy decides what a partner receives and how: its language, its tone and vocabulary, the topics
it never covers, which items a named editor approves first, and how AI involvement is disclosed.
Policies are versioned files reviewed like code; every published item records the version used.
"""

import unicodedata
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.insights import single_line
from fourth_official_contracts.primitives import UtcTimestamp, Version, WireModel

TenantId = Literal["northlight-sport", "tribuna-austral", "rheinblick-sport"]
Locale = Literal["en-GB", "es-MX", "de-DE"]
# What a partner publishes: narrative (insight, recap) is written by agents; the rest is data.
ItemKind = Literal["insight", "recap", "stat", "correction", "score"]
NARRATIVE_KINDS: frozenset[str] = frozenset({"insight", "recap"})
TopicId = Literal[
    "injury_speculation", "betting", "transfer_rumour", "referee_criticism", "off_field"
]
DisclosureMode = Literal["label-all", "label-unless-approved", "eu-strict"]
Template = Literal["lower_third", "stat_card", "correction_strap", "score_bug"]
# Each partner broadcasts in one locale.
TENANT_LOCALES: dict[str, str] = {
    "northlight-sport": "en-GB",
    "tribuna-austral": "es-MX",
    "rheinblick-sport": "de-DE",
}
# The graphic that carries each kind of item.
TEMPLATE_FOR: dict[str, str] = {
    "insight": "lower_third",
    "recap": "lower_third",
    "stat": "stat_card",
    "correction": "correction_strap",
    "score": "score_bug",
}
CorrectionBehaviour = Literal["auto-amend", "retract-and-notify", "escalate"]


def _nfc(text: str) -> str:
    # One spelling per word: "é" typed as one character or as "e" plus an accent compare equal.
    return unicodedata.normalize("NFC", text)


def _line(text: str) -> str:
    single_line(text)
    return text


# A word or short phrase in any of the partners' languages: letters, spaces, hyphens, apostrophes.
Term = Annotated[
    str,
    StringConstraints(min_length=1, max_length=40, pattern=r"^[^\W\d_]+(?:[ '-][^\W\d_]+)*$"),
    AfterValidator(_nfc),
]
EditorName = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Za-z.' -]{1,59}$")]


def _unique(values: tuple[str, ...], what: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{what} must not repeat")


class TenantPolicy(WireModel):
    tenant_id: TenantId
    version: Version
    display_name: Annotated[
        str, StringConstraints(min_length=1, max_length=60), AfterValidator(_line)
    ]
    locale: Locale
    tone: Annotated[tuple[Term, ...], Field(min_length=1, max_length=6, strict=False)]
    prefer_terms: Annotated[tuple[Term, ...], Field(max_length=50, strict=False)]
    avoid_terms: Annotated[tuple[Term, ...], Field(max_length=50, strict=False)]
    blocked_topics: Annotated[tuple[TopicId, ...], Field(max_length=5, strict=False)]
    approval_required: Annotated[tuple[ItemKind, ...], Field(max_length=5, strict=False)]
    disclosure_mode: DisclosureMode
    latency_budget_ms: Annotated[int, Field(ge=1000, le=30_000)]
    max_items_per_minute: Annotated[int, Field(ge=1, le=30)]
    templates: Annotated[tuple[Template, ...], Field(min_length=1, max_length=4, strict=False)]
    correction_behaviour: CorrectionBehaviour

    @model_validator(mode="after")
    def _coherent(self) -> "TenantPolicy":
        for values, what in (
            (self.tone, "tone"),
            (self.prefer_terms, "preferred terms"),
            (self.avoid_terms, "avoided terms"),
            (self.blocked_topics, "blocked topics"),
            (self.approval_required, "approval rules"),
            (self.templates, "templates"),
        ):
            _unique(values, what)
        clash = {t.casefold() for t in self.prefer_terms} & {t.casefold() for t in self.avoid_terms}
        if clash:
            raise ValueError("a term cannot be both preferred and avoided")
        if self.locale != TENANT_LOCALES[self.tenant_id]:
            raise ValueError(f"{self.tenant_id} broadcasts in {TENANT_LOCALES[self.tenant_id]}")
        if "correction_strap" not in self.templates:
            raise ValueError("every partner shows corrections: correction_strap is required")
        for kind in self.approval_required:
            if TEMPLATE_FOR[kind] not in self.templates:
                raise ValueError(f"{kind} items need the {TEMPLATE_FOR[kind]} template")
        return self


class Disclosure(WireModel):
    """How AI involvement is shown on an item: the label (rendered by code, never by a model)."""

    label: (
        Annotated[str, StringConstraints(min_length=1, max_length=100), AfterValidator(_line)]
        | None
    )
    mode: DisclosureMode
    # ai_generated: written by agents, not reviewed; ai_assisted_reviewed: approved by a named
    # editor; data: no words written by an agent.
    reason: Literal["ai_generated", "ai_assisted_reviewed", "data"]

    @model_validator(mode="after")
    def _labelled_as_the_mode_requires(self) -> "Disclosure":
        # Only a reviewed item under label-unless-approved may go without a label.
        unlabelled_allowed = self.reason == "data" or (
            self.reason == "ai_assisted_reviewed" and self.mode == "label-unless-approved"
        )
        if self.label is None and not unlabelled_allowed:
            raise ValueError(f"{self.mode} requires a label on this item")
        return self


class Approval(WireModel):
    """A named editor's decision on an item before it goes on air."""

    editor: EditorName
    decided_at: UtcTimestamp
    decision: Literal["approved", "rejected"]


TENANT_POLICY_ADAPTER: TypeAdapter[TenantPolicy] = TypeAdapter(TenantPolicy)


def parse_tenant_policy(raw: object) -> TenantPolicy:
    """Validate decoded data (camelCase keys only) into a tenant policy."""
    return TENANT_POLICY_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
