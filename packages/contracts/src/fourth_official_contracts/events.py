"""Match events: the synthetic feed the pipeline ingests (stage one, Ingest).

Every event shares an envelope (identity, order, version, clock). The `type` field selects one of
the concrete event models below; `parse_match_event` validates raw wire data into the right one.
"""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from fourth_official_contracts.primitives import (
    ClubCode,
    EventId,
    MatchClock,
    MatchId,
    PitchPoint,
    PlayerId,
    Ratio,
    Score,
    Seq,
    SpeedKmh,
    UtcTimestamp,
    Version,
    WireModel,
    club_of,
    match_of,
)


class EventEnvelope(WireModel):
    """Identity and ordering shared by every event."""

    event_id: EventId
    match_id: MatchId
    # Strictly increasing per match; consumers reorder by it.
    seq: Seq
    # Starts at 1; a correction republishes the event with a higher version.
    version: Version
    clock: MatchClock
    wall_clock: UtcTimestamp

    @model_validator(mode="after")
    def _references_stay_in_the_match(self) -> "EventEnvelope":
        if match_of(self.event_id) != self.match_id:
            raise ValueError(f"event {self.event_id} does not belong to match {self.match_id}")
        # Every `*_event_id` reference (shot, foul, VAR target) must point at another event of
        # the same match.
        for name in type(self).model_fields:
            if name.endswith("_event_id") and name != "event_id":
                reference = getattr(self, name)
                if reference is None:
                    continue
                if match_of(reference) != self.match_id:
                    raise ValueError(f"{name} {reference} belongs to another match")
                if reference == self.event_id:
                    raise ValueError(f"{name} cannot reference the event itself")
        return self


class PlayerAction(EventEnvelope):
    """An action by one player for their team."""

    team_id: ClubCode
    player_id: PlayerId

    @model_validator(mode="after")
    def _player_plays_for_team(self) -> "PlayerAction":
        if club_of(self.player_id) != self.team_id:
            raise ValueError(f"player {self.player_id} does not play for {self.team_id}")
        return self


def _require_opponent(team_id: str, player_id: str, role: str) -> None:
    if club_of(player_id) == team_id:
        raise ValueError(f"{role} {player_id} must play for the opposing team")


class PassEvent(PlayerAction):
    type: Literal["PASS"]
    origin: PitchPoint
    end: PitchPoint
    outcome: Literal["complete", "incomplete"]
    receiver_id: PlayerId | None
    kind: Literal["ground", "lofted", "through", "cross", "switch"]
    speed_kmh: SpeedKmh

    @model_validator(mode="after")
    def _receiver_matches_outcome(self) -> "PassEvent":
        if self.outcome == "complete":
            if self.receiver_id is None:
                raise ValueError("a completed pass needs a receiver")
            if club_of(self.receiver_id) != self.team_id or self.receiver_id == self.player_id:
                raise ValueError("the receiver must be a different player on the same team")
        elif self.receiver_id is not None:
            raise ValueError("an incomplete pass has no receiver")
        return self


class CarryEvent(PlayerAction):
    type: Literal["CARRY"]
    origin: PitchPoint
    end: PitchPoint


class ShotEvent(PlayerAction):
    type: Literal["SHOT"]
    origin: PitchPoint
    body_part: Literal["right_foot", "left_foot", "head", "other"]
    outcome: Literal["goal", "saved", "off_target", "blocked", "woodwork"]
    speed_kmh: SpeedKmh
    # Share of the shooter's space taken by defenders at the moment of the shot.
    pressure: Ratio


class SaveEvent(PlayerAction):
    type: Literal["SAVE"]
    shot_event_id: EventId


class TackleEvent(PlayerAction):
    type: Literal["TACKLE"]
    at: PitchPoint
    opponent_id: PlayerId
    outcome: Literal["won", "lost"]

    @model_validator(mode="after")
    def _opponent_is_on_other_team(self) -> "TackleEvent":
        _require_opponent(self.team_id, self.opponent_id, "opponent")
        return self


class InterceptionEvent(PlayerAction):
    type: Literal["INTERCEPTION"]
    at: PitchPoint


class ClearanceEvent(PlayerAction):
    type: Literal["CLEARANCE"]
    at: PitchPoint


class PressureEvent(PlayerAction):
    type: Literal["PRESSURE"]
    at: PitchPoint
    target_id: PlayerId
    intensity: Ratio

    @model_validator(mode="after")
    def _target_is_on_other_team(self) -> "PressureEvent":
        _require_opponent(self.team_id, self.target_id, "target")
        return self


class FoulEvent(PlayerAction):
    type: Literal["FOUL"]
    at: PitchPoint
    victim_id: PlayerId

    @model_validator(mode="after")
    def _victim_is_on_other_team(self) -> "FoulEvent":
        _require_opponent(self.team_id, self.victim_id, "victim")
        return self


class CardEvent(PlayerAction):
    type: Literal["CARD"]
    card: Literal["yellow", "second_yellow", "red"]
    foul_event_id: EventId | None


class OffsideEvent(PlayerAction):
    type: Literal["OFFSIDE"]
    at: PitchPoint


class SetPieceEvent(PlayerAction):
    type: Literal["SET_PIECE"]
    kind: Literal["kick_off", "corner", "free_kick", "throw_in", "goal_kick", "penalty"]
    at: PitchPoint


class SubstitutionEvent(EventEnvelope):
    type: Literal["SUBSTITUTION"]
    team_id: ClubCode
    player_off_id: PlayerId
    player_on_id: PlayerId

    @model_validator(mode="after")
    def _both_players_play_for_team(self) -> "SubstitutionEvent":
        for player in (self.player_off_id, self.player_on_id):
            if club_of(player) != self.team_id:
                raise ValueError(f"player {player} does not play for {self.team_id}")
        if self.player_off_id == self.player_on_id:
            raise ValueError("a player cannot replace themselves")
        return self


class PossessionChangeEvent(EventEnvelope):
    type: Literal["POSSESSION_CHANGE"]
    # The team that gains possession.
    team_id: ClubCode
    cause: Literal["tackle", "interception", "out_of_play", "foul", "shot_end", "other"]


class GoalEvent(EventEnvelope):
    type: Literal["GOAL"]
    # The team credited with the goal (for an own goal, the opponent of the scorer).
    team_id: ClubCode
    scorer_id: PlayerId
    assist_id: PlayerId | None
    own_goal: bool
    # The shot that produced the goal; own goals often have none.
    shot_event_id: EventId | None
    score_after: Score

    @model_validator(mode="after")
    def _credit_is_consistent(self) -> "GoalEvent":
        if self.shot_event_id is None and not self.own_goal:
            raise ValueError("a goal that is not an own goal needs its shot_event_id")
        scorer_club = club_of(self.scorer_id)
        if self.own_goal == (scorer_club == self.team_id):
            raise ValueError(
                "the scorer's club must match the credited team, unless it is an own goal"
            )
        if self.assist_id is not None:
            if self.assist_id == self.scorer_id:
                raise ValueError("a player cannot assist their own goal")
            if self.own_goal or club_of(self.assist_id) != self.team_id:
                raise ValueError(
                    "the assist must come from the credited team, and own goals have none"
                )
        return self


class VarCheckEvent(EventEnvelope):
    type: Literal["VAR_CHECK"]
    target_event_id: EventId
    reason: Literal["goal", "penalty", "red_card", "mistaken_identity"]


class VarDecisionEvent(EventEnvelope):
    type: Literal["VAR_DECISION"]
    target_event_id: EventId
    decision: Literal["confirmed", "overturned"]
    reason: Literal["offside", "foul", "handball", "none"]

    @model_validator(mode="after")
    def _reason_matches_decision(self) -> "VarDecisionEvent":
        if (self.decision == "confirmed") != (self.reason == "none"):
            raise ValueError("a confirmed decision has reason 'none'; an overturned one names why")
        return self


class PeriodStartEvent(EventEnvelope):
    type: Literal["PERIOD_START"]


class PeriodEndEvent(EventEnvelope):
    type: Literal["PERIOD_END"]


MatchEvent = Annotated[
    PassEvent
    | CarryEvent
    | ShotEvent
    | SaveEvent
    | TackleEvent
    | InterceptionEvent
    | ClearanceEvent
    | PressureEvent
    | FoulEvent
    | CardEvent
    | OffsideEvent
    | SetPieceEvent
    | SubstitutionEvent
    | PossessionChangeEvent
    | GoalEvent
    | VarCheckEvent
    | VarDecisionEvent
    | PeriodStartEvent
    | PeriodEndEvent,
    Field(discriminator="type"),
]
"""Any match event, discriminated by `type`."""

MATCH_EVENT_TYPES: tuple[type[EventEnvelope], ...] = (
    PassEvent,
    CarryEvent,
    ShotEvent,
    SaveEvent,
    TackleEvent,
    InterceptionEvent,
    ClearanceEvent,
    PressureEvent,
    FoulEvent,
    CardEvent,
    OffsideEvent,
    SetPieceEvent,
    SubstitutionEvent,
    PossessionChangeEvent,
    GoalEvent,
    VarCheckEvent,
    VarDecisionEvent,
    PeriodStartEvent,
    PeriodEndEvent,
)
"""Every concrete event model; use with `isinstance` (the `MatchEvent` union cannot be)."""

# Errors must never echo untrusted input back into logs or responses.
MATCH_EVENT_ADAPTER: TypeAdapter[MatchEvent] = TypeAdapter(
    MatchEvent, config=ConfigDict(hide_input_in_errors=True)
)


def parse_match_event(raw: object) -> MatchEvent:
    """Validate decoded wire data (a dict from JSON, camelCase keys) into its event model."""
    return MATCH_EVENT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)


def parse_match_event_json(data: str | bytes) -> MatchEvent:
    """Validate JSON text from the wire into its event model."""
    return MATCH_EVENT_ADAPTER.validate_json(data, by_alias=True, by_name=False)
