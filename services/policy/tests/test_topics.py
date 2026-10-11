"""Blocked topics: words that signal a topic a partner never covers, in each partner's language."""

import pytest

from fourth_official_contracts import TenantId, TenantPolicy
from fourth_official_policy import blocked_topics_in, bundled_store


def policy(tenant: TenantId) -> TenantPolicy:
    return bundled_store().get(tenant).policy


@pytest.mark.parametrize(
    ("tenant", "text", "topic"),
    [
        ("northlight-sport", "The striker looks injured after that tackle.", "injury_speculation"),
        (
            "northlight-sport",
            "A hamstring problem may explain the slow start.",
            "injury_speculation",
        ),
        ("northlight-sport", "The odds on a comeback have shortened.", "betting"),
        ("tribuna-austral", "El delantero parece lesionado tras la entrada.", "injury_speculation"),
        ("tribuna-austral", "Las apuestas ya favorecen la remontada.", "betting"),
        (
            "rheinblick-sport",
            "Der Stürmer wirkt nach dem Zweikampf verletzt.",
            "injury_speculation",
        ),
        ("rheinblick-sport", "Die Wettquoten sprechen für das Heimteam.", "betting"),
    ],
)
def test_seeded_temptations_are_caught(tenant: TenantId, text: str, topic: str) -> None:
    assert topic in blocked_topics_in(text, policy(tenant))


def test_a_topic_the_partner_allows_is_not_reported() -> None:
    # Northlight does not block referee criticism.
    assert (
        blocked_topics_in("The referee got that one badly wrong.", policy("northlight-sport")) == []
    )


@pytest.mark.parametrize(
    ("tenant", "text"),
    [
        ("northlight-sport", "A crisp pass splits the back line."),
        ("tribuna-austral", "Golazo de contragolpe al minuto final."),
        ("rheinblick-sport", "Das Pressing lässt nach."),
    ],
)
def test_ordinary_football_passes(tenant: TenantId, text: str) -> None:
    assert blocked_topics_in(text, policy(tenant)) == []


# Ordinary football language each lexicon must leave alone (found in review).
@pytest.mark.parametrize(
    ("tenant", "text"),
    [
        ("northlight-sport", "Northgate win against the odds."),
        ("northlight-sport", "The knock-on effect is a quick transition."),
        ("northlight-sport", "A knock to the crossbar keeps it level."),
        ("northlight-sport", "A better ball finds the runner."),
        ("tribuna-austral", "El resultado parcial favorece al local."),
        ("tribuna-austral", "Un robo de balón inicia el contragolpe."),
        ("tribuna-austral", "Tras un robo del balón llega el gol."),
        ("rheinblick-sport", "Der Ballbesitz betrug zuletzt deutlich mehr."),
        ("rheinblick-sport", "Bei diesem Wetter ist das Pressing schwer."),
        ("rheinblick-sport", "Eine Regelverletzung führt zum Freistoß."),
        ("rheinblick-sport", "Die Gäste lösen sich aus dem Pressing und ablösen wird keiner."),
        ("rheinblick-sport", "Der Wettbewerb ist eng, der Wettkampf hart."),
        ("rheinblick-sport", "Die Passquote steigt nach dem Wechsel."),
    ],
)
def test_everyday_football_language_is_not_a_blocked_topic(tenant: TenantId, text: str) -> None:
    assert blocked_topics_in(text, policy(tenant)) == []


@pytest.mark.parametrize(
    ("tenant", "text", "topic"),
    [
        ("tribuna-austral", "El delantero sufre una lesion.", "injury_speculation"),
        ("tribuna-austral", "Nos robaron el partido.", "referee_criticism"),
        ("tribuna-austral", "El árbitro parcial decide todo.", "referee_criticism"),
        ("rheinblick-sport", "Die Sportwetten sehen das Heimteam vorn.", "betting"),
        ("rheinblick-sport", "Eine Muskelverletzung bremst den Stürmer.", "injury_speculation"),
        ("northlight-sport", "The betting odds have shortened.", "betting"),
    ],
)
def test_unaccented_spellings_and_listed_compounds_are_caught(
    tenant: TenantId, text: str, topic: str
) -> None:
    assert topic in blocked_topics_in(text, policy(tenant))
