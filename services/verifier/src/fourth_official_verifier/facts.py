"""Everything the Verifier may treat as true about a match at a moment."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from fourth_official_contracts import GoalEvent, MetricSnapshot
from fourth_official_stats.prepare import PreparedMatch


@dataclass(frozen=True, slots=True)
class MatchFacts:
    match: PreparedMatch
    # Display names: the two clubs playing, and every player in both squads.
    club_names: Mapping[str, str]
    player_names: Mapping[str, str]
    # Metric snapshots that may be cited, by ID.
    snapshots: Mapping[str, MetricSnapshot]
    # Events voided by corrections, and snapshots superseded by restatements.
    voided: frozenset[str] = field(default_factory=frozenset)
    superseded: frozenset[str] = field(default_factory=frozenset)

    def score_at(self, as_of_seq: int) -> tuple[int, int]:
        """Home and away goals up to and including `as_of_seq`, without voided goals."""
        home = away = 0
        for event in self.match.events:
            if event.seq > as_of_seq:
                break
            if isinstance(event, GoalEvent) and event.event_id not in self.voided:
                if event.team_id == self.match.context.home:
                    home += 1
                else:
                    away += 1
        return home, away
