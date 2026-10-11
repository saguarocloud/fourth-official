"""Checks on the words of a claim, outside its references, in the claim's language.

Claim text is ordinary football language: printable characters of the language (plus typographic
quotes and dashes), capitals only for known terms and a closed set of sentence openers, no numbers
in any form, no names written out, and no wording about the future. English text also uses only
words from the vocabulary allowlist. The rules for each language are in `languages.py`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from fourth_official_contracts import CLUB_NAMES
from fourth_official_verifier.languages import ENGLISH, Language, fold

_TOKEN = re.compile(r"\{\{[^{}]*\}\}")
_TYPOGRAPHIC = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
        "\u202f": " ",
    }
)
# A number and anything stuck to it ("3", "2-0", "1st", "90th").
_NUMBERS = re.compile(r"[0-9][0-9A-Za-z]*")
_SENTENCE_END = re.compile(r"[.!?;:]\s+|[.!?;:]$|\s-\s")
# Stands in for a reference: not a word, not a number, and never the start of a sentence.
_HOLE = " ⁣ "


@dataclass(frozen=True, slots=True)
class TextProblems:
    unsupported: bool = False
    numbers: list[str] = field(default_factory=list)
    raw_names: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    unknown_words: list[str] = field(default_factory=list)
    future: list[str] = field(default_factory=list)


def _plain(text: str, language: Language) -> str:
    # A reference may take the language's possessive: "{{club:NGT}}'s", "{{club:NGT}}s".
    ending = f"(?:{language.possessive})?" if language.possessive else ""
    return re.sub(r"\{\{[^{}]*\}\}" + ending, _HOLE, text).translate(_TYPOGRAPHIC)


def _allowed(language: Language) -> re.Pattern[str]:
    return re.compile(rf"^[\x20-\x7e{re.escape(language.letters)}]*$")


def _name_forms(player_names: Iterable[str]) -> set[str]:
    forms = {n.casefold() for n in CLUB_NAMES.values()} | {c.casefold() for c in CLUB_NAMES}
    for name in player_names:
        forms.add(name.casefold())
        forms |= {part.casefold() for part in re.split(r"[\s-]+", name) if len(part) > 1}
    return forms


def _strip_names(plain: str, forms: set[str]) -> tuple[str, list[str]]:
    found = []
    for form in sorted(forms, key=len, reverse=True):
        pattern = re.compile(rf"(?<![\w]){re.escape(form)}(?![\w])", re.IGNORECASE)
        if pattern.search(plain):
            found.append(form)
            plain = pattern.sub(_HOLE, plain)
    return plain, found


def _sentence_starts(plain: str) -> set[int]:
    starts = {0}
    for end in _SENTENCE_END.finditer(plain):
        starts.add(end.end())
    return starts


def _is_opener(match: re.Match[str], starts: set[int], plain: str, leading: str) -> bool:
    before = plain[: match.start()].rstrip(leading)
    return match.start() in starts or len(before) in starts or not before


# Phrases that state a count, allowed only where cited evidence states the same: the caller
# passes them in when it has checked the evidence.
SECOND_YELLOW: dict[str, re.Pattern[str]] = {
    "en-GB": re.compile(r"\bsecond[ -]yellow\b", re.IGNORECASE),
    "es-MX": re.compile(r"\bsegunda (?:tarjeta )?amarilla\b", re.IGNORECASE),
    "de-DE": re.compile(r"\bzweiten? gelben?(?: karte)?\b", re.IGNORECASE),
}


def check_text(
    text: str,
    player_names: Iterable[str],
    *,
    evidenced: Iterable[re.Pattern[str]] = (),
    language: Language = ENGLISH,
) -> TextProblems:
    """Everything wrong with the words of a claim or headline in `language`. `evidenced` phrases
    are accepted because the evidence the text cites states them."""
    plain = _plain(text, language)
    if not _allowed(language).match(plain.replace(_HOLE, " ")):
        return TextProblems(unsupported=True)
    plain, raw = _strip_names(plain, _name_forms(player_names))
    if language.place_phrases is not None:
        plain = language.place_phrases.sub(_HOLE, plain)
    for phrase in evidenced:
        plain = phrase.sub(_HOLE, plain)
    numbers = _NUMBERS.findall(plain)
    plain = _NUMBERS.sub(_HOLE, plain)
    names: list[str] = []
    unknown: list[str] = []
    starts = _sentence_starts(plain)
    for match in language.word.finditer(plain):
        word = match.group(0).strip("'-")
        lower = word.lower()
        if language.states_number(word):
            numbers.append(word)
        elif language.capitalised(word):
            continue
        elif word[0].isupper():
            opener = _is_opener(match, starts, plain, language.leading)
            if not (opener and fold(word) in language.openers):
                names.append(word)
        elif language.known is not None and not language.known(lower):
            unknown.append(word)
    if language.number_phrases is not None:
        numbers += language.number_phrases.findall(fold(plain))
    future = language.future_in(plain)
    return TextProblems(False, numbers, raw, names, unknown, future)
