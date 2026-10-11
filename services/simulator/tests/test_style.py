"""Team style: the four dials that make tactics visible in the data."""

import dataclasses

import pytest

from fourth_official_simulator.style import TeamStyle


def test_a_style_holds_four_bounded_dials() -> None:
    style = TeamStyle(pressing=0.8, directness=0.3, width=0.6, tempo=0.7)

    assert style.pressing == 0.8


@pytest.mark.parametrize("field", ["pressing", "directness", "width", "tempo"])
@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_dials_outside_zero_to_one_are_refused(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        TeamStyle(**{"pressing": 0.5, "directness": 0.5, "width": 0.5, "tempo": 0.5, field: value})


def test_a_style_change_returns_a_new_style() -> None:
    style = TeamStyle(pressing=0.8, directness=0.3, width=0.6, tempo=0.7)

    tired = style.with_changes(pressing=0.3)

    assert (style.pressing, tired.pressing) == (0.8, 0.3)
    assert tired.tempo == style.tempo


def test_styles_are_immutable() -> None:
    style = TeamStyle(pressing=0.5, directness=0.5, width=0.5, tempo=0.5)

    with pytest.raises(dataclasses.FrozenInstanceError):
        style.pressing = 0.9  # type: ignore[misc]
