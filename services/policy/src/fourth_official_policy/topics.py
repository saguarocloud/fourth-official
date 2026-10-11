"""Blocked topics: words that signal a topic a partner never covers, per language.

A first, deterministic screen on every item a partner receives. Every term matches as a whole
word or phrase, after folding case and accents (so "lesion" is caught as well as "lesión").
German compounds are listed one by one rather than matched as stems: a stem inside a word catches
ordinary football too ("betrug" in "Ballbesitz betrug", "wette" in "Wetter"). Bare words with a
football meaning are left out or only listed in phrases ("robo de balón" is winning the ball;
"resultado parcial" is the half-time score; "against the odds" is not betting).
"""

import re
import unicodedata

from fourth_official_contracts import Locale, TenantPolicy, TopicId

_TERMS: dict[Locale, dict[TopicId, tuple[str, ...]]] = {
    "en-GB": {
        "injury_speculation": (
            "injured", "injury", "injuries", "hamstring", "limping", "stretcher", "concussion",
            "fitness doubt", "muscle strain", "ankle problem", "knee problem",
        ),
        "betting": (
            "betting", "bets", "bet on", "bookmaker", "bookmakers", "bookies", "wager",
            "punters", "odds on", "odds-on",
        ),
        "transfer_rumour": (
            "transfer rumour", "transfer rumours", "transfer talk", "release clause",
            "contract talks", "linked with a move",
        ),
        "referee_criticism": (
            "disgraceful", "scandalous", "robbed", "cheated", "biased", "incompetent",
        ),
        "off_field": ("arrest", "arrested", "court case", "nightclub", "police"),
    },
    "es-MX": {
        "injury_speculation": (
            "lesión", "lesiones", "lesionado", "lesionada", "molestias musculares",
            "isquiotibiales", "camilla", "conmoción",
        ),
        "betting": ("apuesta", "apuestas", "momios", "casa de apuestas", "casas de apuestas"),
        "transfer_rumour": (
            "fichaje", "traspaso", "rumor de fichaje", "rumores", "cláusula de rescisión",
        ),
        "referee_criticism": (
            "árbitro parcial", "arbitraje parcial", "fue un robo", "robaron", "vergonzoso",
            "escandaloso", "sesgado",
        ),
        "off_field": ("arresto", "arrestado", "tribunal", "policía", "escándalo"),
    },
    "de-DE": {
        "injury_speculation": (
            "verletzt", "verletzung", "verletzungen", "muskelverletzung",
            "oberschenkelverletzung", "knieverletzung", "knöchelverletzung", "zerrung",
            "muskelzerrung", "gehirnerschütterung",
        ),
        "betting": (
            "wette", "wetten", "sportwetten", "wettquote", "wettquoten", "wettanbieter",
            "buchmacher",
        ),
        "transfer_rumour": (
            "transfergerücht", "transfergerüchte", "wechselgerüchte", "ablösesumme",
            "ausstiegsklausel", "transferpoker",
        ),
        "referee_criticism": (
            "schiedsrichterskandal", "betrügerisch", "parteiisch", "verpfiffen",
        ),
        "off_field": ("verhaftet", "verhaftung", "polizei", "gerichtsverfahren"),
    },
}  # fmt: skip


def fold(text: str) -> str:
    """Case and accents folded away: "Lesión", "lesion" and "LESIÓN" compare equal."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _pattern(terms: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(fold(term)) for term in terms)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)")


_PATTERNS: dict[Locale, dict[TopicId, re.Pattern[str]]] = {
    locale: {topic: _pattern(terms) for topic, terms in topics.items()}
    for locale, topics in _TERMS.items()
}


def blocked_topics_in(text: str, policy: TenantPolicy) -> list[TopicId]:
    """The partner's blocked topics the text touches, in policy order."""
    folded = fold(text)
    patterns = _PATTERNS[policy.locale]
    return [topic for topic in policy.blocked_topics if patterns[topic].search(folded)]
