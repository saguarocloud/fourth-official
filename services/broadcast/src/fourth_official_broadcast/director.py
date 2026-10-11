"""The director: when each graphic comes in and goes out, for one partner.

- Graphics of one template never overlap: the next waits for the screen to clear.
- A correction strap has its own slot, so it never waits for a lower third.
- Narrative (lower thirds) keeps to the partner's pace: at most `max_per_minute` starts in any
  sixty seconds of play.
- A graphic stays within its half, and one that would start more than ninety seconds after its
  moment is dropped: late news airs as stale news.

The schedule is immutable: `place` returns the next one.
"""

from dataclasses import dataclass, field, replace

from fourth_official_contracts import MatchClock, Template
from fourth_official_contracts.primitives import FIRST_HALF_MINUTES, SECOND_HALF_MINUTES

ON_SCREEN_SECONDS: dict[Template, int] = {
    "lower_third": 12,
    "stat_card": 10,
    "correction_strap": 20,
    "score_bug": 30,
}
MAX_DELAY_SECONDS = 90
# A graphic with less time than this left in the half is not worth airing; a correction is.
MIN_ON_SCREEN_SECONDS = 3
PACE_WINDOW_SECONDS = 60
_LAST_SECOND = {1: FIRST_HALF_MINUTES[1] * 60 + 59, 2: SECOND_HALF_MINUTES[1] * 60 + 59}

Timing = tuple[MatchClock, MatchClock]


@dataclass(frozen=True, slots=True)
class Schedule:
    max_per_minute: int
    period: int = 1
    # When each template's slot is free again, in seconds of the current period.
    free_at: tuple[tuple[Template, int], ...] = ()
    # When recent narrative graphics started, in seconds of the current period, in order.
    narrative: tuple[int, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.max_per_minute < 1:
            raise ValueError("a partner's pace must allow at least one graphic a minute")


def _seconds(clock: MatchClock) -> int:
    return clock.minute * 60 + clock.second


def _clock(period: int, seconds: int) -> MatchClock:
    return MatchClock(period=period, minute=seconds // 60, second=seconds % 60)  # type: ignore[arg-type]


def _paced(start: int, starts: tuple[int, ...], limit: int) -> int:
    """The first second at or after `start` with room for another narrative graphic."""
    while True:
        recent = [s for s in starts if start - PACE_WINDOW_SECONDS < s <= start]
        if len(recent) < limit:
            return start
        start = recent[-limit] + PACE_WINDOW_SECONDS


def place(schedule: Schedule, template: Template, at: MatchClock) -> tuple[Schedule, Timing | None]:
    """When a `template` graphic for a moment published at `at` airs, or None if it would air
    stale or past the end of the half; and the schedule after it."""
    if at.period != schedule.period:
        schedule = Schedule(max_per_minute=schedule.max_per_minute, period=at.period)
    free = dict(schedule.free_at)
    start = max(_seconds(at), free.get(template, 0))
    narrative = template == "lower_third"
    if narrative:
        start = _paced(start, schedule.narrative, schedule.max_per_minute)
    last = _LAST_SECOND[at.period]
    if start - _seconds(at) > MAX_DELAY_SECONDS or start >= last:
        return schedule, None
    end = min(start + ON_SCREEN_SECONDS[template], last)
    if end - start < MIN_ON_SCREEN_SECONDS and template != "correction_strap":
        return schedule, None
    free[template] = end
    # Only starts within the pace window matter for the next graphic.
    kept = tuple(s for s in schedule.narrative if s > start - PACE_WINDOW_SECONDS)
    placed = replace(
        schedule,
        free_at=tuple(sorted(free.items())),
        narrative=(*kept, start) if narrative else schedule.narrative,
    )
    return placed, (_clock(at.period, start), _clock(at.period, end))
