"""Moments shown by a metric moving: a press that collapses or surges."""

from events import pass_, pressure
from fourth_official_contracts import MatchEvent, Moment
from fourth_official_moments.detector import detect
from fourth_official_moments.rules import (
    COOLDOWN_MINUTES,
    PRESS_COLLAPSE_RATIO,
    PRESS_SURGE_RATIO,
)
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import prepare

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")


def pressing_match(presses_per_minute: dict[range, int], *, minutes: int = 44) -> list[MatchEvent]:
    """Each minute NGT makes five passes and HCY presses as often as asked, every ten seconds."""
    events: list[MatchEvent] = []
    for minute in range(minutes):
        presses = next((n for span, n in presses_per_minute.items() if minute in span), 0)
        for slot in range(6):
            seq = len(events) + 1
            if slot < 5:
                events.append(pass_(seq, minute, "NGT", second=slot * 10))
            if slot < presses:
                events.append(pressure(len(events) + 1, minute, "HCY", "NGT", second=slot * 10 + 5))
    return events


def shift_moments(events: list[MatchEvent]) -> list[Moment]:
    _, found = detect(prepare(CTX, events))
    return [m for m in found if m.shifts]


def test_a_steady_press_is_not_a_moment() -> None:
    assert shift_moments(pressing_match({range(44): 2})) == []


def test_a_press_that_stops_is_a_collapse_once_it_has_held_for_three_minutes() -> None:
    (collapse,) = shift_moments(pressing_match({range(25): 3}))
    (shift,) = collapse.shifts

    assert (collapse.kind, collapse.club) == ("pressing_collapse", "HCY")
    # The 5-minute rate has to fall below the threshold, then stay there for two more checks.
    assert 27 <= collapse.clock.minute <= 31
    assert shift.metric == "pressing_intensity"
    assert shift.before == 0.6  # three presses per five opponent passes
    assert shift.after <= PRESS_COLLAPSE_RATIO * shift.before
    assert shift.before_snapshot_id.endswith(f"-15m-s{_seq_at(collapse, 5):04d}-v1")
    assert "-5m-" in shift.after_snapshot_id
    assert collapse.metric_snapshot_ids == (shift.before_snapshot_id, shift.after_snapshot_id)
    assert collapse.event_ids == ()


def test_a_press_that_starts_is_a_surge() -> None:
    (surge,) = shift_moments(pressing_match({range(25): 1, range(25, 44): 4}))

    assert (surge.kind, surge.club) == ("pressing_surge", "HCY")
    assert surge.shifts[0].after >= PRESS_SURGE_RATIO * surge.shifts[0].before


def test_a_press_too_light_to_matter_cannot_collapse() -> None:
    # One press every two minutes is not a press; its disappearance is not news.
    light = {range(0, 25, 2): 1}

    assert shift_moments(pressing_match(light)) == []


def test_the_same_story_is_not_told_twice_within_the_cooldown() -> None:
    # Collapse at about 27', recovery, collapse again well inside the cooldown.
    flicker = {range(25): 3, range(30, 34): 3}

    assert [m.kind for m in shift_moments(pressing_match(flicker))] == ["pressing_collapse"]
    assert COOLDOWN_MINUTES >= 10


def test_shift_rules_wait_until_there_is_a_full_baseline() -> None:
    # No press at all for the first ten minutes, then pressing: too early to call anything.
    assert shift_moments(pressing_match({range(10, 18): 3}, minutes=19)) == []


def _seq_at(moment: Moment, minutes_before: int) -> int:
    """The seq of the last event at or before `minutes_before` minutes ahead of the moment."""
    events = pressing_match({range(25): 3})
    match = prepare(CTX, events)
    now = match.seconds(match.by_seq[moment.as_of_seq])
    return max(e.seq for e in match.events if match.seconds(e) <= now - minutes_before * 60)
