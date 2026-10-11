"""Checks on the words of a claim: no numbers or names written out instead of referenced."""

import re
from collections.abc import Iterable

from fourth_official_contracts import CLUB_NAMES
from fourth_official_verifier.vocabulary import SENTENCE_OPENERS, TERMS

_TOKEN = re.compile(r"\{\{[^{}]*\}\}")
_DIGITS = re.compile(r"[0-9]+")
_NUMBER_WORDS = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    r"sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
    r"hundred|dozen|twice|thrice)\b",
    re.IGNORECASE,
)
_SENTENCE = re.compile(r"[.!?;:]\s+|[.!?;:]$")
# Words may contain apostrophes (straight or typographic) and hyphens.
_WORD = re.compile("[^\\W\\d_][\\w'\u2019-]*")
# Stands in for a reference so that it is not read as a word or a number.
_HOLE = " \u2063 "


def without_markup(text: str) -> str:
    return _TOKEN.sub(_HOLE, text)


def bare_numbers(text: str) -> list[str]:
    """Numbers written in the text instead of rendered from evidence."""
    plain = without_markup(text)
    return [*_DIGITS.findall(plain), *(m.group(0) for m in _NUMBER_WORDS.finditer(plain))]


def raw_names(text: str, player_names: Iterable[str]) -> list[str]:
    """Club or player names written out instead of referenced."""
    plain = without_markup(text)
    names = [*CLUB_NAMES.values(), *player_names]
    surnames = [n.split()[-1] for n in player_names if " " in n]
    return [
        name
        for name in sorted({*names, *surnames}, key=len, reverse=True)
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", plain)
    ]


def unverified_names(text: str, known: Iterable[str]) -> list[str]:
    """Capitalised words that could be names nobody referenced: anything mid-sentence that is
    not a known term, and sentence openers that are not common words."""
    plain = without_markup(text)
    for name in sorted(known, key=len, reverse=True):
        plain = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", _HOLE, plain)
    found: list[str] = []
    for sentence in _SENTENCE.split(plain):
        words = _WORD.findall(sentence)
        for index, word in enumerate(words):
            if not word[0].isupper() or word in TERMS:
                continue
            opener = index == 0 and sentence.lstrip().startswith(word)
            if opener and word.lower() in SENTENCE_OPENERS:
                continue
            found.append(word)
    return found
