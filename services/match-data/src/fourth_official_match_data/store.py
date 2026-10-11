"""Where match facts come from. The demo store replays the fixed matchday in memory; a store
backed by Cosmos DB will expose the same interface."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Protocol

from fourth_official_contracts import CLUB_NAMES, Correction, EventVoided, MatchEvent, Moment
from fourth_official_moments.detector import detect
from fourth_official_simulator.demo import demo_matchday
from fourth_official_simulator.engine import play
from fourth_official_simulator.squads import Player
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import PreparedMatch, prepare


class MatchDataError(ValueError):
    """A request the store cannot answer. The message is safe to show to the caller."""


@dataclass(frozen=True, slots=True)
class MatchRecord:
    match: PreparedMatch
    club_names: Mapping[str, str]
    players: Mapping[str, Player]
    moments: tuple[Moment, ...]
    corrections: tuple[Correction, ...]
    # The last event published so far: nothing after it is ever returned.
    live_seq: int

    def resolve(self, as_of_seq: int | None) -> MatchEvent:
        """The last published event at or before `as_of_seq` (default: the live position)."""
        if as_of_seq is not None and as_of_seq > self.live_seq:
            # Whether that seq exists later is itself a fact about the future: never say.
            raise MatchDataError("that point of the match has not been published yet")
        limit = self.live_seq if as_of_seq is None else as_of_seq
        published = [e for e in self.match.events if e.seq <= limit]
        if not published:
            raise MatchDataError("no event has been published at that point")
        return published[-1]

    def voided_at(self, event: MatchEvent) -> frozenset[str]:
        """Events voided by corrections issued by the time of `event`."""
        return frozenset(
            c.target_event_id
            for c in self.corrections
            if isinstance(c, EventVoided) and c.issued_at <= event.wall_clock
        )


class MatchStore(Protocol):
    def match_ids(self) -> tuple[str, ...]: ...

    def record(self, match_id: str) -> MatchRecord: ...


@dataclass(frozen=True, slots=True)
class InMemoryStore:
    records: Mapping[str, MatchRecord]

    def match_ids(self) -> tuple[str, ...]:
        return tuple(self.records)

    def record(self, match_id: str) -> MatchRecord:
        found = self.records.get(match_id)
        if found is None:
            raise MatchDataError("unknown match")
        return found

    def with_live_seq(self, match_id: str, live_seq: int) -> "InMemoryStore":
        """The same store with one match replayed only up to `live_seq`."""
        updated = replace(self.record(match_id), live_seq=live_seq)
        return InMemoryStore(MappingProxyType({**self.records, match_id: updated}))


def demo_store() -> InMemoryStore:
    """The fixed demo matchday, fully played."""
    records: dict[str, MatchRecord] = {}
    for setup in demo_matchday():
        home, away = setup.home.squad, setup.away.squad
        played = play(setup)
        match = prepare(MatchContext(setup.match_id, home.club, away.club), played.events)
        records[setup.match_id] = MatchRecord(
            match=match,
            club_names=MappingProxyType({c: CLUB_NAMES[c] for c in (home.club, away.club)}),
            players=MappingProxyType({p.player_id: p for s in (home, away) for p in s.players}),
            moments=detect(match)[1],
            corrections=played.corrections,
            live_seq=match.events[-1].seq,
        )
    return InMemoryStore(MappingProxyType(records))
