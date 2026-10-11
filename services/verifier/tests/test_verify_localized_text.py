"""The Verifier reads a localised insight in its own language, with the same guarantees."""

import pytest

from fourth_official_contracts import parse_localized_insight
from fourth_official_verifier import verify
from verifier_fixtures import FACTS, GOAL_MOMENT, POSSESSION, insight_wire, localized_wire

VALUE = "{{value:" + POSSESSION.snapshot_id + "}}"


def codes(tenant: str, headline: str, *texts: str) -> list[str]:
    localized = parse_localized_insight(localized_wire(insight_wire(), tenant, headline, *texts))
    return [f.code for f in verify(localized, GOAL_MOMENT, FACTS).findings]


def test_a_spanish_insight_passes_in_spanish() -> None:
    assert (
        codes(
            "tribuna-austral",
            "Gol de {{club:HCY}}",
            "{{player:HCY-09}} adelanta a {{club:HCY}} en el {{minute:12}}: {{score}}.",
            f"{{{{club:HCY}}}} tiene el {VALUE} del balón.",
        )
        == []
    )


def test_a_german_insight_passes_in_german() -> None:
    assert (
        codes(
            "rheinblick-sport",
            "Tor für {{club:HCY}}",
            "{{player:HCY-09}} bringt {{club:HCY}} in der {{minute:12}} mit {{score}} in Führung.",
            f"{{{{club:HCY}}}} hat {VALUE} Ballbesitz.",
        )
        == []
    )


@pytest.mark.parametrize(
    ("tenant", "first", "code"),
    [
        ("tribuna-austral", "{{club:HCY}} marca dos goles.", "BARE_NUMBER"),
        ("tribuna-austral", "Messi adelanta a {{club:HCY}}.", "UNVERIFIED_NAME"),
        ("tribuna-austral", "{{club:HCY}} ganará el partido.", "FUTURE_WORDING"),
        ("rheinblick-sport", "{{club:HCY}} trifft zweimal.", "BARE_NUMBER"),
        ("rheinblick-sport", "Müller bringt {{club:HCY}} in Führung.", "UNVERIFIED_NAME"),
    ],
)
def test_a_localised_insight_keeps_the_guarantees(tenant: str, first: str, code: str) -> None:
    assert code in codes(tenant, "{{club:HCY}}", first, f"{{{{club:HCY}}}} {VALUE}.")
