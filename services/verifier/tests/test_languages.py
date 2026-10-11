"""Claim text in Spanish and German keeps the guarantees English text has: no number written out,
no name written out, nothing about the future, and only printable characters of the language.

Spanish and German have no lowercase allowlist (see ADR-010): their guarantees are about numbers,
names and the future, and every reference is checked against the canonical insight separately.
"""

import re

import pytest

from fourth_official_simulator.names import BLOCKLIST, FIRST_NAMES, LAST_NAMES
from fourth_official_verifier.languages import GERMAN, LANGUAGES, SPANISH
from fourth_official_verifier.text import check_text
from verifier_fixtures import PLAYERS

NAMES = list(PLAYERS.values())


def problems(text: str, language: object) -> dict[str, list[str] | bool]:
    found = check_text(text, NAMES, language=language)  # type: ignore[arg-type]
    return {
        name: value
        for name in ("unsupported", "numbers", "raw_names", "names", "unknown_words", "future")
        if (value := getattr(found, name))
    }


def test_each_partner_locale_has_its_language() -> None:
    assert set(LANGUAGES) == {"en-GB", "es-MX", "de-DE"}


@pytest.mark.parametrize(
    "text",
    [
        "{{player:HCY-09}} marca para {{club:HCY}} en el {{minute:12}}: {{score}}.",
        "Golazo de {{club:HCY}} tras un contragolpe rápido.",
        "¡Qué presión de {{club:NGT}}! El balón llega al área.",
        "Tras la pausa, {{club:NGT}} baja la intensidad del pressing.",
        "El VAR anula el gol de {{club:HCY}} por fuera de juego.",
        "Gran ocasión: {{player:HCY-09}} remata y el portero desvía.",
        "{{club:HCY}} recupera el balón en campo rival.",
    ],
)
def test_ordinary_spanish_passes(text: str) -> None:
    assert problems(text, SPANISH) == {}


@pytest.mark.parametrize(
    "text",
    [
        "{{player:HCY-09}} trifft in der {{minute:12}} für {{club:HCY}} zum {{score}}.",
        "Nach dem Ballgewinn kontert {{club:HCY}} schnell über die Flanke.",
        "Das Pressing von {{club:NGT}} lässt deutlich nach.",
        "{{club:NGT}}s Pressing lässt nach, der Druck sinkt.",
        "Der Videobeweis nimmt das Tor von {{club:HCY}} wegen Abseits zurück.",
        "Große Torchance: {{player:HCY-09}} schießt, der Torwart pariert.",
    ],
)
def test_ordinary_german_passes(text: str) -> None:
    assert problems(text, GERMAN) == {}


@pytest.mark.parametrize(
    ("text", "language", "kind"),
    [
        # Numbers in any form are references.
        ("{{club:HCY}} marca dos goles.", SPANISH, "numbers"),
        ("{{club:HCY}} logra un doblete en la primera mitad.", SPANISH, "numbers"),
        ("{{club:HCY}} remata 3 veces.", SPANISH, "numbers"),
        ("{{club:HCY}} trifft zweimal.", GERMAN, "numbers"),
        ("{{player:HCY-09}} schnürt einen Doppelpack in der ersten Halbzeit.", GERMAN, "numbers"),
        ("{{club:HCY}} hat 60 Prozent Ballbesitz.", GERMAN, "numbers"),
        # Names are references; an unknown capitalised word is treated as a name.
        ("Messi marca para {{club:HCY}}.", SPANISH, "names"),
        ("El balón llega a Gutiérrez en el área.", SPANISH, "names"),
        ("Müller trifft für {{club:HCY}}.", GERMAN, "names"),
        ("Der Ball kommt zu Schweinsteiger im Strafraum.", GERMAN, "names"),
        # Nothing about what happens later.
        ("{{club:HCY}} va a ganar este partido.", SPANISH, "future"),
        ("{{club:HCY}} ganará con este ritmo.", SPANISH, "future"),
        ("{{club:HCY}} wird dieses Spiel gewinnen.", GERMAN, "future"),
        ("Bald fällt das nächste Tor für {{club:HCY}}.", GERMAN, "future"),
    ],
)
def test_spanish_and_german_keep_the_guarantees(text: str, language: object, kind: str) -> None:
    assert kind in problems(text, language)


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("{{club:HCY}} marca un gol " + chr(0x202E) + ".", SPANISH),
        ("{{club:HCY}} trifft. 日本", GERMAN),
    ],
)
def test_only_the_language_s_printable_characters_pass(text: str, language: object) -> None:
    assert problems(text, language) == {"unsupported": True}


def test_a_squad_name_written_out_is_a_raw_name_in_any_language() -> None:
    scorer = PLAYERS["HCY-09"]

    assert "raw_names" in problems(f"{scorer} marca para {{{{club:HCY}}}}.", SPANISH)
    assert "raw_names" in problems(f"{scorer} trifft für {{{{club:HCY}}}}.", GERMAN)


def test_german_werden_is_refused_even_as_become() -> None:
    """A known cost: "wird" is the future auxiliary and also "becomes". Telling them apart needs
    grammar; refusing both costs a rephrase ("lässt nach"), never a claim about the future."""
    assert "future" in problems("Das Pressing wird schwächer.", GERMAN)


def _name_parts() -> set[str]:
    return {
        part
        for name in (*FIRST_NAMES, *LAST_NAMES, *BLOCKLIST)
        for part in re.split(r"[\s-]+", name)
        if len(part) > 1
    }


def test_no_squad_name_passes_as_a_german_noun_or_an_opener() -> None:
    clashes = sorted(
        part
        for part in _name_parts()
        if GERMAN.capitalised(part)
        or part.lower() in GERMAN.openers
        or part.lower() in SPANISH.openers
    )

    assert clashes == []


def test_no_number_word_opens_a_sentence() -> None:
    for language in (SPANISH, GERMAN):
        assert not (language.openers & language.number_words)


# Bypasses found in review: every one must be refused.
SPANISH_NUMBERS = """
el equipo dio veinticuatro pases | hubo quinientos pases | hubo cuatrocientos pases |
hubo novecientos pases | con veintiséis remates | con veintiún remates | treinta y uno |
el equipo dio dieciseis pases | el vigésimo minuto | la décima ocasión | el undécimo córner |
un onceavo | un cuarteto de remates | un quinteto | un par de remates | una decena de pases |
un centenar de pases | un millar | un tercio | cuádruple cambio | un dúo | un trío
"""
GERMAN_NUMBERS = """
dreiundzwanzig Pässe | fünfundzwanzig Pässe | einundzwanzig Pässe | achtundvierzig Pässe |
zweihundert Pässe | dreitausend Fans | einhundert Pässe | dreissig Pässe | die zehnte Chance |
die achte Chance | im achten Versuch | die siebte Ecke | die neunte Ecke | die zwölfte Ecke |
die elfte Ecke | die sechste Ecke | im sechsten Versuch | das sechstes | die zwanzigste Minute |
die dreißigste Minute | die fünfundvierzigste Minute | die achtzehnte Ecke | Hunderte Fans |
elfmal | achtmal | zehnmal | ein Zweier | die doppelte Anzahl | zwo | zweitens | drittens |
erstens | die Viererkette
"""
SPANISH_FUTURE = """
el equipo ganaría | el equipo marcaría | tras el gol ganaría el partido |
está por marcar | está a punto de marcar | luego marca | después marca | enseguida llega |
en breve llega | a continuación llega el gol | más adelante | tarde o temprano | marcaré |
ganarás
"""
GERMAN_FUTURE = """
er würde treffen | er dürfte treffen | er will treffen | er soll treffen | gleich trifft er |
er zieht gleich ab | kurz darauf trifft er | danach trifft er | zum Ende | noch vor der Pause |
bis zur Pause | anschließend | nachher | alsbald | fortan
"""


def _cases(text: str) -> list[str]:
    return [case.strip() for case in text.split("|") if case.strip()]


@pytest.mark.parametrize(
    ("text", "language", "kind"),
    [(t, SPANISH, "numbers") for t in _cases(SPANISH_NUMBERS)]
    + [(t, GERMAN, "numbers") for t in _cases(GERMAN_NUMBERS)]
    + [(t, SPANISH, "future") for t in _cases(SPANISH_FUTURE)]
    + [(t, GERMAN, "future") for t in _cases(GERMAN_FUTURE)],
)
def test_review_bypasses_are_refused(text: str, language: object, kind: str) -> None:
    assert kind in problems(text, language)


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("La victoria de {{club:HCY}} llega con alegría.", SPANISH),
        ("La mayoría de los pases de {{club:HCY}} van atrás.", SPANISH),
        ("Después de la recuperación, {{club:HCY}} remata.", SPANISH),
        ("{{club:HCY}} gewinnt jeden Zweikampf.", GERMAN),
        ("Vor der Pause dominiert {{club:HCY}}.", GERMAN),
    ],
)
def test_ordinary_words_near_the_new_rules_still_pass(text: str, language: object) -> None:
    assert problems(text, language) == {}


@pytest.mark.parametrize("word", ["Müllers", "Kroosen", "Schweinsteigers", "Seitze"])
def test_case_endings_only_extend_known_nouns_never_names(word: str) -> None:
    assert not GERMAN.capitalised(word)


# Second review round.
@pytest.mark.parametrize(
    ("text", "language", "kind"),
    [
        ("el decimoquinto córner", SPANISH, "numbers"),
        ("el vigesimoprimer minuto", SPANISH, "numbers"),
        ("tras el pitido final", SPANISH, "future"),
        ("{{club:HCY}} juega mañana", SPANISH, "future"),
        ("{{club:HCY}} decide esta noche", SPANISH, "future"),
        ("er trifft hinterher", GERMAN, "future"),
        ("spätestens dann trifft er", GERMAN, "future"),
        ("das bevorstehende Tor", GERMAN, "future"),
        ("{{club:HCY}} trifft erstmals", GERMAN, "numbers"),
        ("ein einmaliger Lauf", GERMAN, "numbers"),
        ("nullkommafünf Tore", GERMAN, "numbers"),
    ],
)
def test_second_round_bypasses_are_refused(text: str, language: object, kind: str) -> None:
    assert kind in problems(text, language)


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Ein Gegentor nimmt {{club:HCY}} die Luft.", GERMAN),
        ("Mit Schwung und Einsatz kommt die Heimelf über die Außenbahn.", GERMAN),
        ("Der Torschütze jubelt.", GERMAN),
        ("Er zieht ab. Sie verteidigen tief.", GERMAN),
        ("Viel Druck kommt von {{club:HCY}}. Jedoch fehlt der Abschluss.", GERMAN),
        ("El remate va al segundo palo.", SPANISH),
        ("El centro cae en el primer palo.", SPANISH),
    ],
)
def test_second_round_false_positives_pass(text: str, language: object) -> None:
    assert problems(text, language) == {}


# Found by measuring the Localizer on the demo matchday (scripts/measure-localizer.py).
@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("{{player:HCY-04}} sieht die Rote Karte.", GERMAN),
        ("{{player:HCY-04}} sieht die Gelbe Karte.", GERMAN),
        ("Das Pressing des Gegners lässt nach.", GERMAN),
        ("Die Abwehr des Tors steht.", GERMAN),
        ("Casi marca {{club:HCY}}.", SPANISH),
        ("Se adelanta {{club:HCY}}.", SPANISH),
        ("Muy cerca estuvo {{club:HCY}}.", SPANISH),
        ("Su presión baja.", SPANISH),
    ],
)
def test_words_the_localizer_reached_for_pass(text: str, language: object) -> None:
    assert problems(text, language) == {}


def test_an_inflected_noun_never_hides_a_number() -> None:
    assert "numbers" in problems("die zweiten Pässe", GERMAN)


@pytest.mark.parametrize("word", ["Zehnen", "Hunderte", "Tausenden", "Zweiten"])
def test_a_case_ending_never_turns_a_number_into_a_noun(word: str) -> None:
    assert not GERMAN.capitalised(word)


@pytest.mark.parametrize("word", ["Torss", "Tornen"])
def test_an_ending_follows_the_last_noun_not_a_linking_letter(word: str) -> None:
    assert not GERMAN.capitalised(word)
