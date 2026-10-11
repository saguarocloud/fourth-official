"""Overlay specs for one partner, from text already rendered by code."""

from fourth_official_broadcast.director import Timing
from fourth_official_contracts import (
    ClubCode,
    Correction,
    CorrectionStrap,
    Disclosure,
    EventVoided,
    GoalEvent,
    Locale,
    LocalizedInsight,
    LowerThird,
    MatchClock,
    OverlaySpec,
    ScoreBug,
    TenantId,
)
from fourth_official_contracts.overlays import MAX_HEADLINE_CHARS
from fourth_official_contracts.tenants import TENANT_LOCALES
from fourth_official_verifier import MatchFacts, render
from fourth_official_verifier.render import SCORE_SEPARATOR

# Lower is more urgent: a correction preempts an insight, which preempts the score.
PRIORITY: dict[str, int] = {"correction_strap": 0, "lower_third": 2, "score_bug": 5}

# Correction straps in each language: written with references and rendered by code.
STRAPS: dict[Locale, dict[str, str]] = {
    "en-GB": {
        "void": "CORRECTION: {club} goal at {minute} ruled out",
        "scorer": "CORRECTION: {club} goal at {minute} credited to {player}",
        "amended": "CORRECTION: {club} goal at {minute} amended",
        "unknown": "CORRECTION: an earlier event has been corrected",
    },
    "es-MX": {
        "void": "CORRECCIÓN: anulado el gol de {club} del {minute}",
        "scorer": "CORRECCIÓN: el gol de {club} del {minute} es de {player}",
        "amended": "CORRECCIÓN: corregido el gol de {club} del {minute}",
        "unknown": "CORRECCIÓN: se corrigió una jugada anterior",
    },
    "de-DE": {
        "void": "KORREKTUR: Tor von {club} aus Minute {minute} aberkannt",
        "scorer": "KORREKTUR: Tor von {club} aus Minute {minute} zählt für {player}",
        "amended": "KORREKTUR: Tor von {club} aus Minute {minute} korrigiert",
        "unknown": "KORREKTUR: Eine frühere Szene wurde korrigiert",
    },
}


def correction_strap_text(correction: Correction, facts: MatchFacts, locale: Locale) -> str:
    """What a correction changed, in the partner's language, rendered from the match. Raises
    `RenderError` only if the match facts cannot render the target goal's club or minute."""
    say = STRAPS[locale]
    target = next((e for e in facts.match.events if e.event_id == correction.target_event_id), None)
    if not isinstance(target, GoalEvent):
        return say["unknown"]
    if isinstance(correction, EventVoided):
        key, player = "void", None
    else:
        player = correction.changes.scorer_id
        key = "scorer" if player is not None and player in facts.player_names else "amended"
    text = say[key].format(
        club=f"{{{{club:{target.team_id}}}}}",
        minute=f"{{{{minute:{target.clock.minute}}}}}",
        player=f"{{{{player:{player}}}}}" if player else "",
    )
    last = facts.match.events[-1].seq
    rendered = render(
        text, facts, as_of_seq=last, cited=(), events={target.event_id}, locale=locale
    )
    return rendered if len(rendered) <= MAX_HEADLINE_CHARS else say["unknown"]


def lower_third(
    localized: LocalizedInsight,
    rendered: tuple[str, tuple[str, ...]],
    disclosure: Disclosure,
    timing: Timing,
) -> OverlaySpec:
    """A partner's insight on air: its headline, and its first claim under it."""
    headline, claims = rendered
    if not claims:
        raise ValueError("a lower third shows the insight's first claim; there is none")
    return OverlaySpec(
        item_id=localized.item_id,
        tenant_id=localized.tenant_id,
        locale=localized.locale,
        in_at=timing[0],
        out_at=timing[1],
        priority=PRIORITY["lower_third"],
        content=LowerThird(template="lower_third", headline=headline, line=claims[0]),
        disclosure=disclosure,
        provenance_url=None,
        version=localized.version,
        supersedes=None,
    )


def correction_strap(
    *, tenant_id: TenantId, item_id: str, text: str, timing: Timing
) -> OverlaySpec:
    """A correction on air: the most urgent graphic a partner shows. `text` comes from
    `correction_strap_text` in the partner's own locale (`TENANT_LOCALES[tenant_id]`)."""
    return OverlaySpec(
        item_id=item_id,
        tenant_id=tenant_id,
        locale=TENANT_LOCALES[tenant_id],
        in_at=timing[0],
        out_at=timing[1],
        priority=PRIORITY["correction_strap"],
        content=CorrectionStrap(template="correction_strap", text=text),
        disclosure=None,
        provenance_url=None,
        version=1,
        supersedes=None,
    )


def score_bug(
    *,
    tenant_id: TenantId,
    item_id: str,
    home: ClubCode,
    away: ClubCode,
    score: tuple[int, int],
    clock: MatchClock,
    timing: Timing,
) -> OverlaySpec:
    """The score and clock, in the partner's way of writing a score."""
    locale = TENANT_LOCALES[tenant_id]
    return OverlaySpec(
        item_id=item_id,
        tenant_id=tenant_id,
        locale=locale,
        in_at=timing[0],
        out_at=timing[1],
        priority=PRIORITY["score_bug"],
        content=ScoreBug(
            template="score_bug",
            home=home,
            away=away,
            score=f"{score[0]}{SCORE_SEPARATOR[locale]}{score[1]}",
            clock=f"{clock.minute:02d}:{clock.second:02d}",
        ),
        disclosure=None,
        provenance_url=None,
        version=1,
        supersedes=None,
    )
