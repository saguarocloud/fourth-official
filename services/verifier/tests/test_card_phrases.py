"""'Second yellow' states a count, so it passes only where a cited card event says exactly that."""

from dataclasses import replace

import pytest

from fourth_official_contracts import Moment, parse_insight, parse_localized_insight
from fourth_official_moments.detector import detect
from fourth_official_stats.prepare import prepare
from fourth_official_verifier import verify
from moment_builders import card
from verifier_fixtures import CTX, EVENTS, FACTS, localized_wire


def sent_off(kind: str) -> tuple[Moment, object]:
    # The card builder books HCY-04.
    match = prepare(CTX, (*EVENTS, card(8, 30, "HCY", kind=kind, foul_seq=None)))
    (moment,) = [m for m in detect(match)[1] if m.kind == "red_card"]
    return moment, replace(FACTS, match=match)


def codes_for(text: str, kind: str, *, headline: str = "{{club:HCY}} down a player") -> list[str]:
    moment, facts = sent_off(kind)
    insight = parse_insight(
        {
            "insightId": f"in-{moment.moment_id.removeprefix('mo-')}-a1",
            "matchId": "m42",
            "momentId": moment.moment_id,
            "asOfSeq": moment.as_of_seq,
            "locale": "en",
            "headline": headline,
            "claims": [
                {
                    "claimId": "cl-1",
                    "type": "milestone",
                    "text": text,
                    "evidence": {"eventIds": list(moment.event_ids), "metricSnapshotIds": []},
                }
            ],
            "provenance": {
                "agent": "analyst",
                "promptVersion": "v1.2",
                "model": "fast",
                "producedBy": "model",
            },
        }
    )
    return [f.code for f in verify(insight, moment, facts).findings]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text",
    [
        "{{player:HCY-04}} is sent off after a second yellow card.",
        "A Second Yellow sends {{player:HCY-04}} off.",
    ],
)
def test_a_second_yellow_may_be_named_when_the_card_was_one(text: str) -> None:
    assert codes_for(text, "second_yellow") == []


def test_a_second_yellow_headline_needs_the_card_too() -> None:
    assert (
        codes_for(
            "{{player:HCY-04}} is sent off.",
            "second_yellow",
            headline="Second yellow for {{club:HCY}}",
        )
        == []
    )
    assert "BARE_NUMBER" in codes_for(
        "{{player:HCY-04}} is sent off.", "red", headline="Second yellow for {{club:HCY}}"
    )


def test_a_straight_red_is_not_a_second_yellow() -> None:
    assert "BARE_NUMBER" in codes_for("{{player:HCY-04}} is sent off after a second yellow.", "red")


def test_only_the_card_phrase_is_allowed_not_the_number() -> None:
    assert "BARE_NUMBER" in codes_for("{{player:HCY-04}} is booked a second time.", "second_yellow")


def test_the_second_yellow_must_belong_to_the_player_named() -> None:
    text = "{{player:HCY-09}} sees a second yellow card."

    assert "BARE_NUMBER" in codes_for(text, "second_yellow")


def test_a_second_yellow_for_the_club_names_no_other_player() -> None:
    assert codes_for("{{club:HCY}} lose a player to a second yellow.", "second_yellow") == []


def localized_codes_for(tenant: str, text: str, kind: str) -> list[str]:
    moment, facts = sent_off(kind)
    canonical = {
        "insightId": f"in-{moment.moment_id.removeprefix('mo-')}-a1",
        "matchId": "m42",
        "momentId": moment.moment_id,
        "asOfSeq": moment.as_of_seq,
        "claims": [
            {
                "claimId": "cl-1",
                "type": "milestone",
                "text": "x",
                "evidence": {"eventIds": list(moment.event_ids), "metricSnapshotIds": []},
            }
        ],
    }
    localized = parse_localized_insight(localized_wire(canonical, tenant, "{{club:HCY}}", text))
    return [f.code for f in verify(localized, moment, facts).findings]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tenant", "text"),
    [
        ("tribuna-austral", "{{player:HCY-04}} se va expulsado por segunda amarilla."),
        ("rheinblick-sport", "{{player:HCY-04}} sieht die zweite Gelbe Karte."),
    ],
)
def test_a_second_yellow_is_named_in_each_language_only_with_the_card(
    tenant: str, text: str
) -> None:
    assert localized_codes_for(tenant, text, "second_yellow") == []
    assert "BARE_NUMBER" in localized_codes_for(tenant, text, "red")
