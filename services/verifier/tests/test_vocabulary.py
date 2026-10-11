"""The claim vocabulary: ordinary football English, and never a name or a number."""

import re

import pytest

from fourth_official_simulator.names import BLOCKLIST, FIRST_NAMES, LAST_NAMES
from fourth_official_verifier.vocabulary import NUMBER_WORDS, SENTENCE_OPENERS, known, words


def _name_parts() -> set[str]:
    return {
        part.casefold()
        for name in (*FIRST_NAMES, *LAST_NAMES, *BLOCKLIST)
        for part in re.split(r"[\s-]+", name)
        if part
    }


def test_no_name_from_the_squads_or_the_blocklist_is_an_ordinary_word() -> None:
    clashes = sorted(part for part in _name_parts() if known(part) or part in SENTENCE_OPENERS)

    assert clashes == []


def test_no_number_word_is_in_the_vocabulary() -> None:
    assert not (words() & NUMBER_WORDS)
    assert not any(known(word) for word in NUMBER_WORDS if "-" not in word)


@pytest.mark.parametrize(
    "word",
    [
        "presses",
        "pressed",
        "pressing",
        "stopped",
        "tried",
        "chances",
        "midfielders",
        "team's",
        "opponents'",
        "didn't",
        "build-up",
        "sharper",
        "quickly",
    ],
)
def test_inflections_and_compounds_of_known_words_are_known(word: str) -> None:
    assert known(word)


@pytest.mark.parametrize("word", ["haaland", "xi", "mbappe", "delgado", "brilliantly-xi", "'s"])
def test_anything_else_is_unknown(word: str) -> None:
    assert not known(word)
