"""The deterministic Verifier: an insight passes only if every fact in it is true at its moment."""

from dataclasses import replace

import pytest

from fourth_official_contracts import FindingCode, Insight, parse_verdict
from fourth_official_verifier import verify
from verifier_fixtures import FACTS, GOAL_MOMENT, LATER_POSSESSION, POSSESSION, claim, insight


def codes(subject: Insight, facts: object = FACTS) -> list[FindingCode]:
    verdict = verify(subject, GOAL_MOMENT, facts)  # type: ignore[arg-type]
    return [f.code for f in verdict.findings]


def test_a_true_insight_passes() -> None:
    verdict = verify(insight(), GOAL_MOMENT, FACTS)

    assert verdict.passed
    assert verdict.findings == ()
    assert parse_verdict(verdict.to_wire()) == verdict


# --- Seeded adversarial claims: every one must be blocked ---------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A number the model wrote itself, in digits or in words.
        ("{{club:HCY}} have had 3 shots.", "BARE_NUMBER"),
        ("{{club:HCY}} have had three shots.", "BARE_NUMBER"),
        ("{{club:HCY}} lead 2-0.", "BARE_NUMBER"),
        # A name written out instead of referenced, or invented.
        ("Harbour City strike first.", "RAW_NAME"),
        ("The goal came from Marco Delgado.", "UNVERIFIED_NAME"),
        ("Delgado finished it off for {{club:HCY}}.", "UNVERIFIED_NAME"),
        # References that do not resolve in this match.
        ("{{player:HCY-99}} scored.", "UNKNOWN_PLAYER"),
        ("{{player:SLT-09}} scored.", "UNKNOWN_PLAYER"),
        ("{{club:SLT}} are watching.", "UNKNOWN_CLUB"),
        # Leaking the future: a minute that has not been played yet.
        ("{{club:HCY}} hold on until the {{minute:20}}.", "FUTURE_MINUTE"),
    ],
)
def test_adversarial_claims_are_blocked(text: str, expected: FindingCode) -> None:
    assert expected in codes(insight(claim(text)))


def test_a_raw_player_name_must_be_a_reference() -> None:
    scorer = FACTS.player_names["HCY-11"]

    assert "RAW_NAME" in codes(insight(claim(f"{scorer} scores for {{{{club:HCY}}}}.")))


def test_evidence_from_after_the_moment_is_future_leakage() -> None:
    later = claim(
        "{{club:HCY}} have had {{value:" + LATER_POSSESSION.snapshot_id + "}} of the ball.",
        events=(),
        snapshots=(LATER_POSSESSION.snapshot_id,),
    )
    future_event = claim("{{club:NGT}} reply.", events=("m42-e0007",))

    assert codes(insight(later)) == ["FUTURE_EVIDENCE"]
    assert codes(insight(future_event)) == ["FUTURE_EVIDENCE"]


def test_evidence_must_exist() -> None:
    missing_event = claim("{{club:HCY}} strike.", events=("m42-e0999",))
    missing_snapshot = claim(
        "{{club:HCY}} have had {{value:ms-m42-xg-HCY-5m-s0004-v1}}.",
        events=(),
        snapshots=("ms-m42-xg-HCY-5m-s0004-v1",),
    )

    assert codes(insight(missing_event)) == ["EVIDENCE_NOT_FOUND"]
    assert codes(insight(missing_snapshot)) == ["SNAPSHOT_NOT_FOUND"]


def test_a_voided_event_cannot_be_cited() -> None:
    facts = replace(FACTS, voided=frozenset({"m42-e0004"}))

    assert codes(insight(claim("{{club:HCY}} strike first.")), facts) == ["VOIDED_EVIDENCE"]


def test_a_restated_snapshot_cannot_be_cited() -> None:
    facts = replace(FACTS, superseded=frozenset({POSSESSION.snapshot_id}))

    assert "SUPERSEDED_EVIDENCE" in codes(insight(), facts)


def test_an_undefined_value_cannot_be_quoted() -> None:
    undefined = POSSESSION.model_copy(update={"value": None})
    facts = replace(FACTS, snapshots={POSSESSION.snapshot_id: undefined})

    assert "UNDEFINED_VALUE" in codes(insight(), facts)


def test_the_insight_must_be_about_the_moment() -> None:
    other = GOAL_MOMENT.model_copy(update={"as_of_seq": 3})

    assert [f.code for f in verify(insight(), other, FACTS).findings] == ["MOMENT_MISMATCH"]


def test_the_headline_is_checked_too() -> None:
    findings = verify(insight(headline="Harbour City strike 1st"), GOAL_MOMENT, FACTS).findings

    assert {(f.claim_id, f.code) for f in findings} == {(None, "RAW_NAME"), (None, "BARE_NUMBER")}


def test_ordinary_capitalised_words_are_not_names() -> None:
    text = "After a VAR check, the xG and PPDA tell the story: {{club:HCY}} were better. It shows."

    assert codes(insight(claim(text))) == []


def test_findings_name_the_claim_and_never_exceed_the_contract() -> None:
    noisy = claim(" ".join(["3"] * 60) + " {{club:HCY}}")
    verdict = verify(insight(noisy), GOAL_MOMENT, FACTS)

    assert not verdict.passed
    assert all(f.claim_id == "cl-1" for f in verdict.findings)
    assert parse_verdict(verdict.to_wire()) == verdict


def test_findings_stop_at_the_contract_limit() -> None:
    missing = tuple(f"m42-e{n:04d}" for n in range(100, 164))
    verdict = verify(insight(claim("{{club:HCY}} strike.", events=missing)), GOAL_MOMENT, FACTS)

    assert len(verdict.findings) == 64
