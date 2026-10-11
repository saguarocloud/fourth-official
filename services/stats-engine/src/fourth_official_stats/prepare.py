"""The single entry point to the stats engine: validated, deduplicated, ordered match events on a
monotone timeline. Every metric and snapshot works on a `PreparedMatch`."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fourth_official_contracts import MatchEvent, PeriodEndEvent
from fourth_official_stats.context import MatchContext
from fourth_official_stats.xg import penalty_awards

# Real matches have roughly 2,500-3,000 events; anything far beyond is refused, not processed.
MAX_EVENTS = 5_000
HALF_SECONDS = 45 * 60


@dataclass(frozen=True, slots=True)
class PreparedMatch:
    context: MatchContext
    events: tuple[MatchEvent, ...]
    by_seq: Mapping[int, MatchEvent]
    # When the first half ended on the match clock, added time included.
    first_half_end: int
    # Penalty shots over the whole match and the awards that made them penalties.
    penalty_awards: Mapping[str, str]

    def seconds(self, event: MatchEvent) -> int:
        """Monotone match time: second-half time continues from the end of the first half, so
        first-half added time never overlaps the start of the second half."""
        clock = event.clock.minute * 60 + event.clock.second
        if event.clock.period == 1:
            return clock
        return self.first_half_end + (clock - HALF_SECONDS)


def _latest_versions(events: Iterable[MatchEvent]) -> list[MatchEvent]:
    latest: dict[str, MatchEvent] = {}
    for event in events:
        kept = latest.get(event.event_id)
        if kept is None or event.version > kept.version:
            latest[event.event_id] = event
    return sorted(latest.values(), key=lambda e: e.seq)


def _first_half_end(events: list[MatchEvent]) -> int:
    first_half = [e for e in events if e.clock.period == 1]
    ends = [e for e in first_half if isinstance(e, PeriodEndEvent)]
    last = ends[-1] if ends else (first_half[-1] if first_half else None)
    return max(HALF_SECONDS, last.clock.minute * 60 + last.clock.second) if last else HALF_SECONDS


def prepare(context: MatchContext, events: Iterable[MatchEvent]) -> PreparedMatch:
    """Validate events against the match and put them in order.

    Refuses events from another match or by a club not in it, two different events with the same
    sequence number, and oversized matches. When a corrected event appears in several versions,
    only the latest counts.
    """
    received = list(events)
    if len(received) > MAX_EVENTS:
        raise ValueError(f"too many events ({len(received)} > {MAX_EVENTS})")
    clubs = {context.home, context.away}
    for event in received:
        if event.match_id != context.match_id:
            raise ValueError(f"event {event.event_id} belongs to match {event.match_id}")
        club = getattr(event, "team_id", None)
        if club is not None and club not in clubs:
            raise ValueError(
                f"event {event.event_id} is by {club}, which is not in {context.match_id}"
            )
    ordered = _latest_versions(received)
    by_seq: dict[int, MatchEvent] = {}
    for event in ordered:
        if event.seq in by_seq:
            raise ValueError(
                f"events {by_seq[event.seq].event_id} and {event.event_id} share seq {event.seq}"
            )
        by_seq[event.seq] = event
    return PreparedMatch(
        context=context,
        events=tuple(ordered),
        by_seq=MappingProxyType(by_seq),
        first_half_end=_first_half_end(ordered),
        penalty_awards=MappingProxyType(penalty_awards(ordered)),
    )
