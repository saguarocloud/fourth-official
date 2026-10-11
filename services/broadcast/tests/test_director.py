"""The director times every graphic: one of a kind at a time, a strap never waits, a partner's
pace is respected, and a graphic never airs stale or across the break."""

import pytest

from fourth_official_broadcast import Schedule, place
from fourth_official_contracts import MatchClock


def clock(minute: int, second: int = 0, period: int = 2) -> MatchClock:
    return MatchClock(period=period, minute=minute, second=second)  # type: ignore[arg-type]


def test_a_lower_third_airs_when_its_moment_is_published() -> None:
    _, timing = place(Schedule(max_per_minute=6), "lower_third", clock(61, 5))

    assert timing == (clock(61, 5), clock(61, 17))


def test_graphics_of_a_kind_never_overlap() -> None:
    schedule, _ = place(Schedule(max_per_minute=6), "lower_third", clock(61, 5))
    _, second = place(schedule, "lower_third", clock(61, 10))

    assert second == (clock(61, 17), clock(61, 29))


def test_a_correction_strap_never_waits_for_a_lower_third() -> None:
    schedule, _ = place(Schedule(max_per_minute=6), "lower_third", clock(61, 5))
    _, strap = place(schedule, "correction_strap", clock(61, 10))

    assert strap == (clock(61, 10), clock(61, 30))


def test_a_partner_s_pace_defers_narrative_beyond_its_limit() -> None:
    schedule = Schedule(max_per_minute=2)
    schedule, first = place(schedule, "lower_third", clock(60, 0))
    schedule, second = place(schedule, "lower_third", clock(60, 20))
    _, third = place(schedule, "lower_third", clock(60, 40))

    assert first == (clock(60, 0), clock(60, 12))
    assert second == (clock(60, 20), clock(60, 32))
    assert third == (clock(61, 0), clock(61, 12))


def test_a_graphic_that_would_air_stale_is_dropped() -> None:
    schedule = Schedule(max_per_minute=1)
    schedule, _ = place(schedule, "lower_third", clock(60, 0))
    schedule, late = place(schedule, "lower_third", clock(60, 1))
    assert late == (clock(61, 0), clock(61, 12))
    _, stale = place(schedule, "lower_third", clock(60, 2))

    assert stale is None


def test_a_graphic_never_crosses_the_end_of_a_half() -> None:
    _, near_end = place(Schedule(max_per_minute=6), "lower_third", clock(59, 55, period=1))
    _, past = place(Schedule(max_per_minute=6), "correction_strap", clock(104, 50))

    assert near_end == (clock(59, 55, period=1), clock(59, 59, period=1))
    assert past == (clock(104, 50), clock(104, 59))


def test_a_new_half_clears_what_was_busy() -> None:
    schedule, _ = place(Schedule(max_per_minute=1), "lower_third", clock(47, 0, period=1))
    _, second_half = place(schedule, "lower_third", clock(45, 5))

    assert second_half == (clock(45, 5), clock(45, 17))


@pytest.mark.parametrize("template", ["lower_third", "stat_card", "correction_strap", "score_bug"])
def test_every_template_has_an_on_screen_time_within_the_contract(template: str) -> None:
    _, timing = place(Schedule(max_per_minute=6), template, clock(70))  # type: ignore[arg-type]

    assert timing is not None
    start, end = timing
    assert 0 < (end.minute * 60 + end.second) - (start.minute * 60 + start.second) <= 60


def test_a_graphic_with_only_a_sliver_of_the_half_left_is_dropped() -> None:
    _, sliver = place(Schedule(max_per_minute=6), "lower_third", clock(59, 58, period=1))
    _, strap = place(Schedule(max_per_minute=6), "correction_strap", clock(59, 58, period=1))

    assert sliver is None
    # A correction is worth airing however briefly.
    assert strap == (clock(59, 58, period=1), clock(59, 59, period=1))


def test_a_schedule_needs_a_pace_of_at_least_one() -> None:
    with pytest.raises(ValueError, match="at least one"):
        Schedule(max_per_minute=0)


def test_old_starts_are_forgotten() -> None:
    schedule = Schedule(max_per_minute=6)
    for minute in range(46, 60):
        schedule, _ = place(schedule, "lower_third", clock(minute))

    assert len(schedule.narrative) <= 6
