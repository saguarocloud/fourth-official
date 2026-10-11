"""Checks on the words of a claim, outside its references.

Claim text is ordinary football English: printable ASCII (plus typographic quotes and dashes),
words from the vocabulary allowlist, capitals only for known terms and a closed set of sentence
openers, no numbers in any form, no names written out, and no wording about the future.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from fourth_official_contracts import CLUB_NAMES
from fourth_official_verifier.vocabulary import NUMBER_WORDS, SENTENCE_OPENERS, TERMS, known

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
_ALLOWED = re.compile(r"^[\x20-\x7e]*$")
# A number and anything stuck to it ("3", "2-0", "1st", "90th").
_NUMBERS = re.compile(r"[0-9][0-9A-Za-z]*")
_WORD = re.compile(r"[A-Za-z][A-Za-z'_-]*")
_SENTENCE_END = re.compile(r"[.!?;:]\s+|[.!?;:]$|\s-\s")
# Wording that reaches past the moment an insight is about.
_FUTURE = re.compile(
    r"\b(will|would|shall|soon|later|afterwards?|shortly|finally|eventually|next|going to|"
    r"about to|go on to|goes on to|went on to|full[- ]time|final whistle|final score|"
    r"in the end)\b",
    re.IGNORECASE,
)
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


# A reference may take a possessive: "{{club:NGT}}'s press".
_POSSESSIVE_TOKEN = re.compile(r"\{\{[^{}]*\}\}(?:['\u2019]s\b|s['\u2019])?")


def _plain(text: str) -> str:
    return _POSSESSIVE_TOKEN.sub(_HOLE, text).translate(_TYPOGRAPHIC)


# Football phrases that contain a number word but state no count. Only places qualify: phrases
# about time ("first half", "for the first time") make claims the Verifier cannot check.
_PLACE_PHRASES = re.compile(r"\bfinal[ -]third\b", re.IGNORECASE)


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


def _is_opener(match: re.Match[str], starts: set[int], plain: str) -> bool:
    before = plain[: match.start()].rstrip(" \"'(")
    return match.start() in starts or len(before) in starts or not before


# Phrases that state a count, allowed only where cited evidence states the same: the caller
# passes them in when it has checked the evidence.
SECOND_YELLOW = re.compile(r"\bsecond[ -]yellow\b", re.IGNORECASE)


def check_text(
    text: str, player_names: Iterable[str], *, evidenced: Iterable[re.Pattern[str]] = ()
) -> TextProblems:
    """Everything wrong with the words of a claim or headline. `evidenced` phrases are accepted
    because the evidence the text cites states them."""
    plain = _plain(text)
    if not _ALLOWED.match(plain.replace(_HOLE, " ")):
        return TextProblems(unsupported=True)
    plain, raw = _strip_names(plain, _name_forms(player_names))
    plain = _PLACE_PHRASES.sub(_HOLE, plain)
    for phrase in evidenced:
        plain = phrase.sub(_HOLE, plain)
    numbers = _NUMBERS.findall(plain)
    plain = _NUMBERS.sub(_HOLE, plain)
    names: list[str] = []
    unknown: list[str] = []
    starts = _sentence_starts(plain)
    for match in _WORD.finditer(plain):
        word = match.group(0).strip("'-")
        lower = word.lower()
        if lower in NUMBER_WORDS or any(part in NUMBER_WORDS for part in lower.split("-")):
            numbers.append(word)
        elif word in TERMS:
            continue
        elif word[0].isupper():
            if not (_is_opener(match, starts, plain) and lower in SENTENCE_OPENERS):
                names.append(word)
        elif not known(lower):
            unknown.append(word)
    future = [m.group(0) for m in _FUTURE.finditer(plain)]
    return TextProblems(False, numbers, raw, names, unknown, future)
