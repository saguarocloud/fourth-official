"""What really happened in a benchmark match: the simulator's own events with every correction
applied, as the ground truth to hold published claims against.

This is deliberately not the Verifier's view of the match. The Verifier checks a claim against the
facts known when it was written; the Proving Ground checks what is still on air at full time
against what is finally true, so a correction the pipeline failed to carry through shows up here.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fourth_official_contracts import (
    EventAmended,
    EventVoided,
    GoalEvent,
    MatchEvent,
    VarDecisionEvent,
)
from fourth_official_simulator.engine import SimulatedMatch

# The fields of an event that name a player taking part in it.
_PARTICIPANTS = (
    "player_id",
    "scorer_id",
    "assist_id",
    "receiver_id",
    "victim_id",
    "target_id",
    "opponent_id",
    "player_off_id",
    "player_on_id",
)


@dataclass(frozen=True, slots=True)
class Truth:
    home: str
    # Every event as it finally stands, voided ones included (they still happened on the pitch).
    events: Mapping[str, MatchEvent]
    original: Mapping[str, MatchEvent]
    voided: frozenset[str]
    # Goals VAR overturned during the match, and the event that announced it: from then on the
    # pipeline published the score without them.
    voided_at: Mapping[str, int]

    def participants(self, event_ids: Iterable[str]) -> set[str]:
        """Players taking part in these events, as finally credited. The shot behind a cited goal
        vouches for nobody: the goal says who scored, and a reassignment changes only the goal."""
        cited = [self.events[e] for e in event_ids if e in self.events]
        behind_goals = {e.shot_event_id for e in cited if isinstance(e, GoalEvent)}
        return {
            value
            for event in cited
            if event.event_id not in behind_goals
            for name in _PARTICIPANTS
            if isinstance(value := getattr(event, name, None), str)
        }

    def minutes(self, event_ids: Iterable[str]) -> set[int]:
        return {self.events[e].clock.minute for e in event_ids if e in self.events}

    def score_at(self, seq: int, *, as_published: bool = False) -> tuple[int, int]:
        """(home, away) after every event up to `seq`: as finally true, or as it could be
        published then (without goals VAR had overturned by then)."""
        events = self.original if as_published else self.events
        home = away = 0
        for event in events.values():
            if not isinstance(event, GoalEvent) or event.seq > seq:
                continue
            decided = self.voided_at.get(event.event_id)
            if as_published and decided is not None and decided <= seq:
                continue
            if not as_published and event.event_id in self.voided:
                continue
            if event.team_id == self.home:
                home += 1
            else:
                away += 1
        return home, away


def truth_of(played: SimulatedMatch) -> Truth:
    original = {e.event_id: e for e in played.events}
    events = dict(original)
    voided: set[str] = set()
    for correction in played.corrections:
        if isinstance(correction, EventVoided):
            voided.add(correction.target_event_id)
        elif isinstance(correction, EventAmended):
            target = events[correction.target_event_id]
            changes = correction.changes.model_dump(exclude_none=True, by_alias=False)
            events[target.event_id] = target.model_copy(update=changes)
    voided_at = {
        e.target_event_id: e.seq
        for e in played.events
        if isinstance(e, VarDecisionEvent) and e.decision == "overturned"
    }
    return Truth(
        home=played.ground_truth.home,
        events=MappingProxyType(events),
        original=MappingProxyType(original),
        voided=frozenset(voided),
        voided_at=MappingProxyType(voided_at),
    )
