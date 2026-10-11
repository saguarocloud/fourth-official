"""Overlay specs: each partner's graphics, every word and number rendered by code."""

import pytest

from fourth_official_broadcast import correction_strap_text, lower_third, score_bug
from fourth_official_contracts import (
    Disclosure,
    EventAmended,
    EventVoided,
    MatchClock,
    parse_localized_insight,
)
from fourth_official_match_data import demo_store
from fourth_official_replay import facts_for
from fourth_official_verifier import render_insight
from verifier_fixtures import FACTS, POSSESSION, insight_wire, localized_wire

EN_DASH = chr(0x2013)
AT = (MatchClock(period=1, minute=12, second=5), MatchClock(period=1, minute=12, second=17))
GENERATED = Disclosure(label="Generado con IA", mode="label-all", reason="ai_generated")
VALUE = "{{value:" + POSSESSION.snapshot_id + "}}"
LOCALIZED = parse_localized_insight(
    localized_wire(
        insight_wire(),
        "tribuna-austral",
        "Gol de {{club:HCY}}",
        "{{player:HCY-09}} adelanta a {{club:HCY}} en el {{minute:12}}: {{score}}.",
        f"{{{{club:HCY}}}} tiene el {VALUE} del balón.",
    )
)


def test_a_lower_third_shows_the_rendered_words_and_the_label() -> None:
    headline, claims = render_insight(LOCALIZED, FACTS, "es-MX")

    overlay = lower_third(LOCALIZED, (headline, claims), GENERATED, AT)

    assert overlay.content.template == "lower_third"
    assert (overlay.content.headline, overlay.content.line) == (headline, claims[0])
    assert overlay.item_id == LOCALIZED.item_id
    assert (overlay.tenant_id, overlay.locale) == ("tribuna-austral", "es-MX")
    assert overlay.disclosure == GENERATED
    assert (overlay.in_at, overlay.out_at) == AT


@pytest.mark.parametrize(
    ("locale", "separator"),
    [("en-GB", "" + EN_DASH + ""), ("es-MX", "" + EN_DASH + ""), ("de-DE", ":")],
)
def test_the_score_bug_writes_the_score_the_market_s_way(locale: str, separator: str) -> None:
    overlay = score_bug(
        tenant_id={
            "en-GB": "northlight-sport",
            "es-MX": "tribuna-austral",
            "de-DE": "rheinblick-sport",
        }[locale],  # type: ignore[arg-type]
        item_id="it-northlight-sport-score-m42-s0100",
        home="HCY",
        away="NGT",
        score=(2, 1),
        clock=MatchClock(period=2, minute=67, second=12),
        timing=AT,
    )

    assert overlay.content.score == f"2{separator}1"  # type: ignore[union-attr]
    assert overlay.content.clock == "67:12"  # type: ignore[union-attr]
    assert overlay.disclosure is None


def _demo_corrections() -> tuple[EventVoided, EventAmended]:
    record = demo_store().record("m42")
    void, amendment = record.corrections
    assert isinstance(void, EventVoided)
    assert isinstance(amendment, EventAmended)
    return void, amendment


STRAP_TEXTS = {
    "en-GB": (
        "CORRECTION: Harbour City goal at 67' ruled out",
        "CORRECTION: Harbour City goal at 89' credited to ",
    ),
    "es-MX": (
        "CORRECCIÓN: anulado el gol de Harbour City del 67'",
        "CORRECCIÓN: el gol de Harbour City del 89' es de ",
    ),
    "de-DE": (
        "KORREKTUR: Tor von Harbour City aus Minute 67' aberkannt",
        "KORREKTUR: Tor von Harbour City aus Minute 89' zählt für ",
    ),
}


@pytest.mark.parametrize(
    ("locale", "void_text", "amend_start"),
    [(locale, void, amend) for locale, (void, amend) in STRAP_TEXTS.items()],
)
def test_a_correction_strap_says_what_changed_in_the_partner_s_language(
    locale: str, void_text: str, amend_start: str
) -> None:
    void, amendment = _demo_corrections()
    facts = facts_for(demo_store().record("m42"))

    assert correction_strap_text(void, facts, locale) == void_text  # type: ignore[arg-type]
    amended = correction_strap_text(amendment, facts, locale)  # type: ignore[arg-type]
    assert amended.startswith(amend_start)
    assert len(amended) <= 120


def test_a_correction_to_an_unknown_event_still_has_a_strap() -> None:
    void, _ = _demo_corrections()
    stray = void.model_copy(update={"target_event_id": "m42-e9999"})
    facts = facts_for(demo_store().record("m42"))

    assert correction_strap_text(stray, facts, "de-DE").startswith("KORREKTUR:")
