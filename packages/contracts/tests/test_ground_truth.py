"""Ground truth: what a simulated match's storylines really were, for scoring the pipeline."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import GroundTruth, parse_ground_truth, parse_ground_truth_json


def truth(**overrides: object) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "matchId": "m42",
        "seed": 4207,
        "storyline": "Press collapses, goal ruled out",
        "home": "HCY",
        "away": "NGT",
        "finalScore": {"home": 2, "away": 1},
        "storylines": [
            {
                "kind": "goal",
                "club": "HCY",
                "minute": 12,
                "label": "HCY score",
                "eventIds": ["m42-e0101", "m42-e0102"],
                "correctionIds": [],
                "expectedMetric": None,
                "expectedDirection": None,
            },
            {
                "kind": "pressing_collapse",
                "club": "NGT",
                "minute": 61,
                "label": "NGT press collapses",
                "eventIds": [],
                "correctionIds": [],
                "expectedMetric": "pressing_intensity",
                "expectedDirection": "down",
            },
            {
                "kind": "var_overturn",
                "club": "HCY",
                "minute": 67,
                "label": "HCY goal ruled out for offside",
                "eventIds": ["m42-e1500", "m42-e1501", "m42-e1502"],
                "correctionIds": ["c-m42-01"],
                "expectedMetric": None,
                "expectedDirection": None,
            },
        ],
    }
    return {**wire, **overrides}


def story(index: int, **overrides: object) -> dict[str, Any]:
    wire = truth()
    storylines = list(wire["storylines"])
    storylines[index] = {**storylines[index], **overrides}
    return {**wire, "storylines": storylines}


def test_ground_truth_round_trips_the_wire() -> None:
    parsed = parse_ground_truth(truth())

    assert isinstance(parsed, GroundTruth)
    assert parsed.to_wire() == truth()
    assert parse_ground_truth_json(parsed.model_dump_json()) == parsed


def test_ground_truth_is_immutable() -> None:
    parsed = parse_ground_truth(truth())

    with pytest.raises(ValidationError):
        parsed.seed = 1  # type: ignore[misc]


def test_a_tactical_shift_may_name_any_metric_or_none() -> None:
    named = {"kind": "tactical_shift", "expectedMetric": "field_tilt", "expectedDirection": "up"}
    unnamed = {"kind": "tactical_shift", "expectedMetric": None, "expectedDirection": None}

    assert parse_ground_truth(story(1, **named)).storylines[1].expected_metric == "field_tilt"
    assert parse_ground_truth(story(1, **unnamed)).storylines[1].expected_metric is None


@pytest.mark.parametrize(
    ("wire", "message"),
    [
        (truth(away="HCY"), "differ"),
        (story(0, club="SLT"), "not in the match"),
        (story(0, eventIds=["m7-e0101"]), "belongs to match"),
        (story(0, eventIds=["m42-e0101", "m42-e0101"]), "unique"),
        (story(0, eventIds=[]), "needs the events"),
        (story(2, correctionIds=["c-m42-01", "c-m42-01"]), "unique"),
        (story(2, correctionIds=[]), "needs its correction"),
        (story(1, expectedDirection=None), "together"),
        (story(0, label="line\nbreak"), "label"),
        (truth(seed=-1), "seed"),
        (story(0, minute=131), "minute"),
        (story(1, expectedDirection="up"), "go down"),
        (story(1, expectedMetric=None, expectedDirection=None), "go down"),
        (story(0, expectedMetric="xg", expectedDirection="up"), "expects no metric"),
        (story(1, eventIds=["m42-e0101"]), "cites no events"),
        (story(0, correctionIds=["c-m42-01"]), "has no correction"),
        (story(0, label="bidi \u202e override"), "label"),
        (story(0, label="line \u2028 separator"), "label"),
    ],
)
def test_incoherent_ground_truth_is_refused(wire: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_ground_truth(wire)


def test_errors_never_echo_the_input() -> None:
    with pytest.raises(ValidationError) as caught:
        parse_ground_truth(truth(storyline="x" * 500))

    assert "x" * 50 not in str(caught.value)
