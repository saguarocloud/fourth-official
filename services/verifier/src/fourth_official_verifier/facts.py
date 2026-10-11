"""Everything the Verifier may treat as true about a match, and when each fact became true."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from fourth_official_contracts import GoalEvent, MetricSnapshot
from fourth_official_stats.prepare import PreparedMatch

_NONE: Mapping[str, int] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class MatchFacts:
    match: PreparedMatch
    # Display names: the two clubs playing, and every player in both squads.
    club_names: Mapping[str, str]
    player_names: Mapping[str, str]
    # Metric snapshots that may be cited, by ID.
    snapshots: Mapping[str, MetricSnapshot]
    # Events voided by corrections, and snapshots superseded by restatements, each with the seq
    # from which it counts: nothing is known before it happened.
    voided: Mapping[str, int] = field(default_factory=lambda: _NONE)
    superseded: Mapping[str, int] = field(default_factory=lambda: _NONE)

    def voided_by(self, event_id: str, as_of_seq: int) -> bool:
        return self.voided.get(event_id, as_of_seq + 1) <= as_of_seq

    def superseded_by(self, snapshot_id: str, as_of_seq: int) -> bool:
        return self.superseded.get(snapshot_id, as_of_seq + 1) <= as_of_seq

    def score_at(self, as_of_seq: int) -> tuple[int, int]:
        """Home and away goals as they stood at `as_of_seq`, without goals voided by then."""
        home = away = 0
        for event in self.match.events:
            if event.seq > as_of_seq:
                break
            if isinstance(event, GoalEvent) and not self.voided_by(event.event_id, as_of_seq):
                if event.team_id == self.match.context.home:
                    home += 1
                else:
                    away += 1
        return home, away
