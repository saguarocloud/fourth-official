"""Rendering: code, not a model, turns references into names and numbers."""

from dataclasses import replace

import pytest

from fourth_official_stats.snapshots import SnapshotKey, snapshot
from fourth_official_verifier import format_value, render
from verifier_fixtures import FACTS, MATCH, POSSESSION, insight


def test_references_render_as_names_numbers_minutes_and_the_score() -> None:
    scorer = FACTS.player_names["HCY-11"]
    text = "{{player:HCY-11}} puts {{club:HCY}} ahead in the {{minute:12}}: {{score}}."

    assert (
        render(text, FACTS, as_of_seq=4)
        == f"{scorer} puts Harbour City ahead in the 12': 1\u20130."
    )


def test_the_score_is_the_score_at_the_moment_without_voided_goals() -> None:
    assert render("{{score}}", FACTS, as_of_seq=7) == "1\u20131"
    assert render("{{score}}", FACTS, as_of_seq=3) == "0\u20130"
    assert (
        render("{{score}}", replace(FACTS, voided=frozenset({"m42-e0004"})), as_of_seq=7)
        == "0\u20131"
    )


@pytest.mark.parametrize(
    ("metric", "scope", "expected"),
    [
        ("possession", "HCY", "100%"),
        ("passes", "HCY", "1"),
        ("xg", "HCY", "0.30"),
        ("pressing_intensity", "NGT", "1.00"),
    ],
)
def test_values_are_formatted_by_metric(metric: str, scope: str, expected: str) -> None:
    snap = snapshot(MATCH, as_of_seq=4, key=SnapshotKey(metric, scope, "match"))  # type: ignore[arg-type]
    facts = replace(FACTS, snapshots={snap.snapshot_id: snap})

    assert render("{{value:" + snap.snapshot_id + "}}", facts, as_of_seq=4) == expected


def test_a_whole_insight_renders_claim_by_claim() -> None:
    rendered = render(insight().claims[1].text, FACTS, as_of_seq=4)

    assert rendered == f"Harbour City have had {round(POSSESSION.value * 100)}% of the ball."  # type: ignore[operator]


def test_an_undefined_value_is_never_rendered() -> None:
    undefined = POSSESSION.model_copy(update={"value": None})
    facts = replace(FACTS, snapshots={POSSESSION.snapshot_id: undefined})

    with pytest.raises(ValueError, match="no value"):
        render("{{value:" + POSSESSION.snapshot_id + "}}", facts, as_of_seq=4)


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [("ppda", 8.24, "8.2"), ("control_chaos", 61.6, "62"), ("shots", 7.0, "7")],
)
def test_each_metric_has_its_own_format(metric: str, value: float, expected: str) -> None:
    assert format_value(metric, value) == expected
