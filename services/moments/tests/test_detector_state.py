"""Incremental detection: one state per match, each event read once, as first published."""

import random
from collections.abc import Callable, Iterable
from functools import cache

import pytest

from events import pass_, penalty_awarded, pressure, shot
from fourth_official_contracts import MatchEvent, Moment
from fourth_official_moments.detector import DetectorState, detect
from fourth_official_simulator.engine import simulate
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import PreparedMatch, prepare
from matches import setup
from moment_builders import goal, var_check, var_decision

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")


@cache
def whole(seed: int) -> PreparedMatch:
    return prepare(CTX, simulate(setup(seed)))


def in_pieces(events: tuple[MatchEvent, ...], cuts: list[int]) -> tuple[Moment, ...]:
    state: DetectorState | None = None
    found: list[Moment] = []
    for cut in [*cuts, len(events)]:
        state, more = detect(prepare(CTX, events[:cut]), state)
        found += more
    return tuple(found)


@pytest.mark.parametrize("seed", [7100, 7101, 7102])
def test_random_pieces_find_exactly_what_the_whole_match_does(seed: int) -> None:
    match = whole(seed)
    rng = random.Random(seed)  # noqa: S311 - reproducible test cuts, not security
    for _ in range(4):
        cuts = sorted(rng.sample(range(1, len(match.events)), 6))
        assert in_pieces(match.events, cuts) == detect(match)[1]


def test_feeding_events_one_by_one_finds_what_the_whole_match_does() -> None:
    match = whole(7103)
    head = match.events[:900]

    assert in_pieces(head, list(range(1, len(head)))) == detect(prepare(CTX, head))[1]


def test_a_republished_event_is_not_read_twice() -> None:
    first = (shot(1, 12, "HCY", outcome="goal"), goal(2, 12, "HCY", shot_seq=1, home=1, away=0))
    state, found = detect(prepare(CTX, first))
    republished = goal(3, 13, "HCY", shot_seq=1, home=1, away=0).model_copy(
        update={"event_id": "m42-e0002", "version": 2}
    )

    state, again = detect(prepare(CTX, (*first, republished)), state)

    assert [m.kind for m in found] == ["goal"]
    assert again == ()


def test_state_from_another_match_is_refused() -> None:
    state, _ = detect(prepare(CTX, (pass_(1, 1, "HCY"),)))
    other = MatchContext(match_id="m43", home="KBA", away="ASV")
    other_events = (
        pass_(1, 1, "KBA").model_copy(update={"event_id": "m43-e0001", "match_id": "m43"}),
    )

    with pytest.raises(ValueError, match="m42"):
        detect(prepare(other, other_events), state)


def test_a_var_overturn_cites_only_the_review_that_overturned() -> None:
    events = (
        shot(1, 67, "HCY", outcome="goal"),
        goal(2, 67, "HCY", shot_seq=1, home=1, away=0),
        var_check(3, 67, target_seq=2),
        var_decision(4, 68, target_seq=2, overturned=False),
        var_check(5, 70, target_seq=2),
        var_decision(6, 71, target_seq=2, overturned=True),
    )
    (overturn,) = [m for m in detect(prepare(CTX, events))[1] if m.kind == "var_overturn"]

    assert overturn.event_ids == ("m42-e0002", "m42-e0005", "m42-e0006")


def test_a_penalty_goal_cites_the_award() -> None:
    events = (
        penalty_awarded(1, 30, "HCY"),
        shot(2, 30, "HCY", outcome="goal"),
        goal(3, 30, "HCY", shot_seq=2, home=1, away=0),
    )
    (scored,) = detect(prepare(CTX, events))[1]

    assert scored.event_ids == ("m42-e0001", "m42-e0002", "m42-e0003")


def test_evidence_is_in_seq_order_even_when_ids_are_not() -> None:
    # A shot republished at a later seq keeps its id; evidence follows match order (seq).
    events = (
        pass_(1, 11, "HCY"),
        goal(3, 12, "HCY", shot_seq=9, home=1, away=0),
        shot(9, 13, "HCY", outcome="goal"),
    )
    found = detect(prepare(CTX, events))[1]

    assert [m.event_ids for m in found if m.kind == "goal"] == [("m42-e0003", "m42-e0009")]


def _pressing(minutes: Iterable[int], presses: Callable[[int], int]) -> list[MatchEvent]:
    """One continuous match: each listed minute NGT passes five times and HCY presses as asked."""
    events: list[MatchEvent] = []
    for minute in minutes:
        for slot in range(5):
            events.append(pass_(len(events) + 1, minute, "NGT", second=slot * 10))
            if slot < presses(minute):
                events.append(pressure(len(events) + 1, minute, "HCY", "NGT", second=slot * 10 + 5))
    return events


def _shifts(events: list[MatchEvent]) -> list[Moment]:
    return [m for m in detect(prepare(CTX, events))[1] if m.shifts]


def test_a_press_from_nothing_is_a_surge_without_waiting_for_the_baseline_to_rise() -> None:
    found = _shifts(_pressing(range(40), lambda minute: 0 if minute < 25 else 4))

    assert [m.kind for m in found] == ["pressing_surge"]
    assert found[0].clock.minute <= 29


def test_a_shift_must_hold_for_consecutive_minutes() -> None:
    # After 25', events only every third minute: never three consecutive checks, so no moment.
    minutes = [*range(25), *range(25, 44, 3)]

    assert _shifts(_pressing(minutes, lambda minute: 3 if minute < 25 else 0)) == []


def test_a_collapse_after_half_time_is_found_on_continuous_match_time() -> None:
    # Minutes 45-61 are the second half here; the press stops at 50'.
    (collapse,) = _shifts(_pressing(range(62), lambda minute: 3 if minute < 50 else 0))

    assert (collapse.kind, collapse.clock.period) == ("pressing_collapse", 2)
    assert 52 <= collapse.clock.minute <= 56


def test_a_flicker_of_pressing_from_nothing_is_not_a_surge() -> None:
    # One press every other minute is below the floor of a press at all.
    assert _shifts(_pressing(range(40), lambda minute: int(minute >= 25 and minute % 2 == 0))) == []
