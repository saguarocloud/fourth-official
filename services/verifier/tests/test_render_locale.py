"""Numbers and scores as each partner's audience reads them, formatted by code from CLDR data.

Golden vectors: German writes a decimal comma and a spaced percent sign; Mexican Spanish, like
English, writes a decimal point (CLDR es-MX), not the comma used in Spain.
"""

import pytest

from fourth_official_verifier import format_value, render
from verifier_fixtures import FACTS, POSSESSION

NBSP, EN_DASH = chr(0xA0), chr(0x2013)


@pytest.mark.parametrize(
    ("metric", "value", "locale", "expected"),
    [
        ("pressing_intensity", 0.284, "en-GB", "0.28"),
        ("pressing_intensity", 0.284, "es-MX", "0.28"),
        ("pressing_intensity", 0.284, "de-DE", "0,28"),
        ("possession", 0.54, "en-GB", "54%"),
        ("possession", 0.54, "es-MX", "54%"),
        ("possession", 0.54, "de-DE", "54" + NBSP + "%"),
        ("ppda", 12.46, "de-DE", "12,5"),
        ("passes", 1234.0, "de-DE", "1.234"),
        ("passes", 1234.0, "en-GB", "1,234"),
    ],
)
def test_values_are_written_the_partner_s_way(
    metric: str, value: float, locale: str, expected: str
) -> None:
    assert format_value(metric, value, locale) == expected  # type: ignore[arg-type]


def test_english_is_the_default_and_unchanged() -> None:
    assert format_value("pressing_intensity", 0.284) == "0.28"


@pytest.mark.parametrize(
    ("locale", "expected"),
    [("en-GB", "1" + EN_DASH + "1"), ("es-MX", "1" + EN_DASH + "1"), ("de-DE", "1:1")],
)
def test_the_score_is_written_as_each_market_writes_it(locale: str, expected: str) -> None:
    assert render("{{score}}", FACTS, as_of_seq=7, cited=(), locale=locale) == expected  # type: ignore[arg-type]


def test_a_value_reference_renders_in_the_locale() -> None:
    text = f"{{{{value:{POSSESSION.snapshot_id}}}}}"

    assert (
        render(text, FACTS, as_of_seq=4, cited=[POSSESSION.snapshot_id], locale="de-DE")
        == "100" + NBSP + "%"
    )


def test_minutes_read_the_same_everywhere() -> None:
    for locale in ("en-GB", "es-MX", "de-DE"):
        assert render("{{minute:12}}", FACTS, as_of_seq=4, cited=(), locale=locale) == "12'"
