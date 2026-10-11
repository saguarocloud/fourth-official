"""The words a claim may use outside references: an allowlist, not a denylist.

Anything not in it (a name, a number word, a word from another language) is refused, so the
Verifier never has to guess what an unfamiliar word is. The list lives in `vocabulary.txt`.
"""

from functools import cache
from importlib.resources import files

# Capitalised words allowed anywhere: terms of the game written in capitals.
TERMS = frozenset({"VAR", "PPDA", "xG"})

# Capitalised words allowed only at the start of a sentence: a closed set, none of which is a
# plausible surname (a test checks them against the squad name pools).
SENTENCE_OPENERS = frozenset(
    """
    a after all an at before both by despite each every few for from here however in into it its
    many meanwhile more neither no nobody not nothing on only over possession pressing pressure
    since that the their there these they this those through under when while with without
    as once until across against along among around behind beyond inside outside within
    goal goals penalty chance chances save saved red card cards press collapse surge lead
    equaliser winner comeback control chaos momentum danger pressure tempo shift switch
    offside overturned ruled disallowed denied missed late early
    """.split()  # noqa: SIM905 - a word list reads best as text
)

# Words that state a number. Refused even where they read naturally: numbers are references.
NUMBER_WORDS = frozenset(
    """
    zero nil one two three four five six seven eight nine ten eleven twelve thirteen
    fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy
    eighty ninety hundred thousand million dozen half quarter single double treble triple
    couple pair brace hat-trick hattrick once twice thrice first second third fourth fifth sixth
    seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth
    seventeenth eighteenth nineteenth twentieth thirtieth fortieth fiftieth sixtieth seventieth
    eightieth ninetieth hundredth
    """.split()  # noqa: SIM905 - a word list reads best as text
)

# Only verb and plural inflections are derived. Agent nouns, comparatives and adverbs (-er, -est,
# -ly) are listed explicitly: derived freely they make surnames ("hunter", "turner", "holder").
_SUFFIXES = ("s", "es", "ed", "d", "ing")
# Fixed football phrases, joined by the text check before words are read.
_PHRASES = frozenset({"final_third", "first_half", "second_half", "half_time", "first_time"})


# Sections whose words are used as written: function words and irregular forms do not inflect
# ("and" does not make "anders", "rose" does not make "ross").
_FIXED_SECTIONS = ("Function words", "Irregular forms")


@cache
def _sections() -> dict[str, frozenset[str]]:
    text = files("fourth_official_verifier").joinpath("vocabulary.txt").read_text("utf-8")
    sections: dict[str, set[str]] = {}
    current = "preamble"
    for line in text.splitlines():
        if line.startswith("# ---"):
            current = line.strip("# -")
        elif not line.startswith("#"):
            sections.setdefault(current, set()).update(line.split())
    return {name: frozenset(found) for name, found in sections.items()}


@cache
def words() -> frozenset[str]:
    return frozenset().union(*_sections().values())


@cache
def _inflectable() -> frozenset[str]:
    sections = _sections()
    return frozenset().union(*(w for n, w in sections.items() if n not in _FIXED_SECTIONS))


def _bases(word: str) -> set[str]:
    """Candidate base forms of an inflected word (presses, pressed, pressing, stopped, tried)."""
    candidates = set()
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            stem = word[: -len(suffix)]
            candidates |= {stem, stem + "e"}
            if len(stem) > 2 and stem[-1] == stem[-2]:
                candidates.add(stem[:-1])  # stopped -> stop
            if stem.endswith("i"):
                candidates.add(stem[:-1] + "y")  # tried -> try
    return candidates


@cache
def known(word: str) -> bool:
    """Whether a lowercase word is ordinary football English from the list."""
    if word in words() or _bases(word) & _inflectable() or word in _PHRASES:
        return True
    for possessive in ("'s", "s'"):
        if word.endswith(possessive) and known(word[: -len(possessive)] or "-"):
            return True
    if "-" in word.strip("-"):
        return all(part and known(part) for part in word.split("-"))
    return False
