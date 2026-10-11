"""A partner's insight: the canonical insight in new words, or a template in the partner's language.

A localised insight may change words only. Its claims, claim types, evidence and references must
be the canonical insight's (references in any order, as word order changes in translation); its
headline may drop a fact but never add one. It must avoid the partner's blocked topics and fit
the graphic it airs in.
"""

from typing import Any

import pytest

from fourth_official_contracts import TenantId, parse_insight, parse_localized_insight
from fourth_official_verifier import template_localized, verify, verify_localized
from test_templates import demo
from verifier_fixtures import FACTS, GOAL_MOMENT, POSSESSION, insight_wire, localized_wire

CANONICAL = insight_wire()
VALUE = "{{value:" + POSSESSION.snapshot_id + "}}"
GOOD_ES = (
    "Gol de {{club:HCY}}",
    "{{player:HCY-09}} adelanta a {{club:HCY}} en el {{minute:12}}: {{score}}.",
    f"{{{{club:HCY}}}} tiene el {VALUE} del balón.",
)


def codes(wire: dict[str, Any], blocked: tuple[str, ...] = ()) -> list[str]:
    localized = parse_localized_insight(wire)
    verdict = verify_localized(
        localized,
        parse_insight(CANONICAL),
        GOAL_MOMENT,
        FACTS,
        blocked=lambda text: [w for w in blocked if w in text],
    )
    return [f.code for f in verdict.findings]


def spanish(*texts: str) -> dict[str, Any]:
    return localized_wire(CANONICAL, "tribuna-austral", *texts)


def test_the_same_facts_in_new_words_pass() -> None:
    assert codes(spanish(*GOOD_ES)) == []


def test_references_may_move_within_a_claim() -> None:
    reordered = "En el {{minute:12}}, {{club:HCY}} se adelanta con {{player:HCY-09}}: {{score}}."

    assert codes(spanish(GOOD_ES[0], reordered, GOOD_ES[2])) == []


def test_a_headline_may_drop_a_fact() -> None:
    assert codes(spanish("¡Golazo!", *GOOD_ES[1:])) == []


@pytest.mark.parametrize(
    "first",
    [
        # An added fact: a player the canonical claim does not name.
        "{{player:HCY-09}} y {{player:HCY-04}} adelantan a {{club:HCY}} en el {{minute:12}}: "
        "{{score}}.",
        # A dropped fact: the score is gone.
        "{{player:HCY-09}} adelanta a {{club:HCY}} en el {{minute:12}}.",
        # A repeated fact counts as a change too.
        "{{player:HCY-09}} adelanta a {{club:HCY}} en el {{minute:12}}: {{score}}, {{score}}.",
    ],
)
def test_a_claim_keeps_exactly_its_references(first: str) -> None:
    assert "REFERENCES_CHANGED" in codes(spanish(GOOD_ES[0], first, GOOD_ES[2]))


def test_a_headline_never_adds_a_fact() -> None:
    assert "REFERENCES_CHANGED" in codes(spanish("Gol de {{player:HCY-04}}", *GOOD_ES[1:]))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("claims", 0, "type"), "causal"),
        (("claims", 0, "evidence", "eventIds"), ["m42-e0004"]),
        (("claims", 1, "claimId"), "cl-3"),
    ],
)
def test_claims_and_their_evidence_are_the_canonical_ones(
    path: tuple[str | int, ...], value: object
) -> None:
    wire = spanish(*GOOD_ES)
    target: Any = wire
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    assert "CLAIMS_CHANGED" in codes(wire)


def test_a_localised_insight_must_be_of_the_canonical_one() -> None:
    other = {**spanish(*GOOD_ES), "insightId": CANONICAL["insightId"].replace("-a1", "-a2")}
    other["itemId"] = other["itemId"].replace("-a1-", "-a2-")

    assert "CLAIMS_CHANGED" in codes(other)


def test_a_claim_with_one_fewer_sentence_is_still_the_same_claim_count() -> None:
    wire = spanish(*GOOD_ES)
    wire["claims"] = wire["claims"][:1]

    assert "CLAIMS_CHANGED" in codes(wire)


def test_a_blocked_topic_is_refused() -> None:
    risky = (GOOD_ES[0], GOOD_ES[1], f"{{{{club:HCY}}}} tiene el {VALUE} del balón y apuestas.")

    assert "BLOCKED_TOPIC" in codes(spanish(*risky), blocked=("apuestas",))


def test_text_too_long_for_the_graphic_is_refused() -> None:
    long = GOOD_ES[1].replace("adelanta a", "adelanta " + "muy " * 45 + "a")

    assert "TOO_LONG" in codes(spanish(GOOD_ES[0], long, GOOD_ES[2]))


def test_the_language_guarantees_still_hold() -> None:
    risky = (GOOD_ES[0], GOOD_ES[1], f"{{{{club:HCY}}}} tiene dos veces el {VALUE} del balón.")

    assert "BARE_NUMBER" in codes(spanish(*risky))


# --- Templates in each partner's language -----------------------------------------------------

PARTNERS = [
    ("tribuna-austral", "es-MX"),
    ("rheinblick-sport", "de-DE"),
    ("northlight-sport", "en-GB"),
]


@pytest.mark.parametrize(("tenant", "locale"), PARTNERS)
def test_every_demo_moment_has_a_template_in_each_partner_s_language(
    tenant: TenantId, locale: str
) -> None:
    checked = 0
    for facts, moments in demo():
        for moment in moments:
            canonical = f"in-{moment.moment_id.removeprefix('mo-')}-a1"
            localized = template_localized(
                moment,
                facts,
                tenant_id=tenant,
                insight_id=canonical,
                policy_version=1,
            )
            verdict = verify(localized, moment, facts)
            assert verdict.passed, (tenant, moment.moment_id, verdict.findings)
            assert localized.locale == locale
            assert localized.provenance.produced_by == "template"
            checked += 1
    assert checked >= 17


def test_a_spanish_goal_template_reads_in_spanish() -> None:
    localized = template_localized(
        GOAL_MOMENT,
        FACTS,
        tenant_id="tribuna-austral",
        insight_id=CANONICAL["insightId"],
        policy_version=1,
    )

    assert localized.headline == "Gol de {{club:HCY}}"
    assert "marca para {{club:HCY}}" in localized.claims[0].text
