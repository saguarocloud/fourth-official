"""Overlay specs: a timed, machine-readable description of one broadcast graphic (stage four).

Every text in a spec is already rendered by code in the partner's language. The renderer draws it
as it is; it never formats a number or chooses a word.
"""

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.insights import single_line
from fourth_official_contracts.localized import ItemId
from fourth_official_contracts.primitives import ClubCode, MatchClock, Version, WireModel
from fourth_official_contracts.tenants import TENANT_LOCALES, Disclosure, Locale, TenantId


def _line(text: str) -> str:
    single_line(text)
    return text


def _text(max_length: int) -> object:
    return StringConstraints(min_length=1, max_length=max_length)


# One printable line each, at most the length its place on screen allows.
ScoreText = Annotated[str, _text(7), AfterValidator(_line)]
ClockText = Annotated[str, _text(8), AfterValidator(_line)]
StatValue = Annotated[str, _text(16), AfterValidator(_line)]
StatLabel = Annotated[str, _text(24), AfterValidator(_line)]
CardTitle = Annotated[str, _text(40), AfterValidator(_line)]
# A lower third's headline and its line under it: the longest text a partner's graphic shows.
MAX_HEADLINE_CHARS = 120
MAX_LINE_CHARS = 200
HeadlineLine = Annotated[str, _text(MAX_HEADLINE_CHARS), AfterValidator(_line)]
BodyLine = Annotated[str, _text(MAX_LINE_CHARS), AfterValidator(_line)]


class LowerThird(WireModel):
    template: Literal["lower_third"]
    headline: HeadlineLine
    line: BodyLine


class StatRow(WireModel):
    label: StatLabel
    value: StatValue


class StatCard(WireModel):
    template: Literal["stat_card"]
    title: CardTitle
    rows: Annotated[tuple[StatRow, ...], Field(min_length=1, max_length=3, strict=False)]


class CorrectionStrap(WireModel):
    template: Literal["correction_strap"]
    text: HeadlineLine


class ScoreBug(WireModel):
    template: Literal["score_bug"]
    home: ClubCode
    away: ClubCode
    score: ScoreText
    clock: ClockText


OverlayContent = Annotated[
    LowerThird | StatCard | CorrectionStrap | ScoreBug, Field(discriminator="template")
]
# A plain https URL: a host and a path, no credentials, no characters that hide what it says.
HttpsUrl = Annotated[
    str,
    StringConstraints(
        max_length=300,
        pattern=r"^https://[A-Za-z0-9.-]{1,253}(:[0-9]{1,5})?(/[A-Za-z0-9._~/?#=&%+-]*)?$",
    ),
]
# How long a graphic may stay on screen, in match time.
MAX_ON_SCREEN_SECONDS = 60


def _seconds(clock: MatchClock) -> int:
    return clock.minute * 60 + clock.second


_VERSION = re.compile(r"-v([0-9]+)$")


class OverlaySpec(WireModel):
    item_id: ItemId
    tenant_id: TenantId
    locale: Locale
    in_at: MatchClock
    out_at: MatchClock
    # 0 is the most urgent: a correction strap preempts a lower third.
    priority: Annotated[int, Field(ge=0, le=9)]
    content: OverlayContent
    disclosure: Disclosure | None
    provenance_url: HttpsUrl | None
    version: Version
    supersedes: ItemId | None

    @model_validator(mode="after")
    def _timed_and_versioned(self) -> "OverlaySpec":
        if self.locale != TENANT_LOCALES[self.tenant_id]:
            raise ValueError(f"{self.tenant_id} broadcasts in {TENANT_LOCALES[self.tenant_id]}")
        # Within one half: a graphic never stays up across the break.
        if self.out_at.period != self.in_at.period:
            raise ValueError("a graphic comes in and goes out in the same half")
        on_screen = _seconds(self.out_at) - _seconds(self.in_at)
        if not 0 < on_screen <= MAX_ON_SCREEN_SECONDS:
            raise ValueError(f"a graphic stays up for 1 to {MAX_ON_SCREEN_SECONDS} seconds")
        if self.supersedes is not None:
            self._check_supersedes(self.supersedes)
        return self

    def _check_supersedes(self, earlier: str) -> None:
        if earlier == self.item_id:
            raise ValueError("a graphic cannot supersede itself")
        if not earlier.startswith(f"it-{self.tenant_id}-"):
            raise ValueError("a graphic only supersedes its own partner's items")
        found = _VERSION.search(earlier)
        if found is not None and int(found.group(1)) >= self.version:
            raise ValueError("a graphic only supersedes an earlier version")


OVERLAY_SPEC_ADAPTER: TypeAdapter[OverlaySpec] = TypeAdapter(OverlaySpec)


def parse_overlay_spec(raw: object) -> OverlaySpec:
    """Validate decoded wire data (camelCase keys only) into an overlay spec."""
    return OVERLAY_SPEC_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
