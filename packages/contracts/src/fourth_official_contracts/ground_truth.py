"""Ground truth: what really happened in a simulated match, for scoring the pipeline.

The simulator writes one `GroundTruth` per match next to its event stream. The Proving Ground
benchmark compares what the agents noticed, explained and corrected against it; nothing in the
live pipeline ever reads it.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.corrections import CorrectionId
from fourth_official_contracts.metrics import MetricName
from fourth_official_contracts.primitives import (
    ClubCode,
    EventId,
    MatchId,
    Score,
    WireModel,
    match_of,
)

StorylineKind = Literal[
    "goal",
    "red_card",
    "pressing_collapse",
    "pressing_surge",
    "tactical_shift",
    "var_overturn",
    "scorer_reassigned",
]
# Kinds shown by events, kinds that exist through a correction, and style shifts (no events).
_EVENT_KINDS = frozenset({"goal", "red_card", "var_overturn", "scorer_reassigned"})
_CORRECTION_KINDS = frozenset({"var_overturn", "scorer_reassigned"})
# A pressing story names the metric that shows it and the way it moves.
_PRESSING_DIRECTION = {"pressing_collapse": "down", "pressing_surge": "up"}
# Printable, single-line text for labels and names: no control characters, line or paragraph
# separators, or bidirectional overrides that could disguise text in a UI or log.
Label = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=120,
        pattern=r"^[^\x00-\x1f\x7f\u2028\u2029\u202a-\u202e\u2066-\u2069]+$",
    ),
]
MAX_MINUTE = 130
MAX_STORYLINES = 64


class StorylineTruth(WireModel):
    """One thing that happened, with the events and corrections that prove it."""

    kind: StorylineKind
    club: ClubCode
    # The match minute it happened in (for a reassigned scorer, the goal's minute; the
    # reassignment itself is recorded after the final whistle).
    minute: Annotated[int, Field(ge=0, le=MAX_MINUTE)]
    label: Label
    event_ids: Annotated[tuple[EventId, ...], Field(max_length=16, strict=False)]
    correction_ids: Annotated[tuple[CorrectionId, ...], Field(max_length=4, strict=False)]
    # The metric a good analyst would see move, and which way (style shifts only).
    expected_metric: MetricName | None
    expected_direction: Literal["up", "down"] | None

    @model_validator(mode="after")
    def _evidence_is_coherent(self) -> "StorylineTruth":
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("event IDs must be unique")
        if len(set(self.correction_ids)) != len(self.correction_ids):
            raise ValueError("correction IDs must be unique")
        if self.kind in _EVENT_KINDS and not self.event_ids:
            raise ValueError(f"a {self.kind} storyline needs the events that show it")
        if self.kind not in _EVENT_KINDS and self.event_ids:
            raise ValueError(f"a {self.kind} storyline is a change of style; it cites no events")
        if self.kind in _CORRECTION_KINDS and not self.correction_ids:
            raise ValueError(f"a {self.kind} storyline needs its correction")
        if self.kind not in _CORRECTION_KINDS and self.correction_ids:
            raise ValueError(f"a {self.kind} storyline has no correction")
        if (self.expected_metric is None) != (self.expected_direction is None):
            raise ValueError("expected metric and direction come together")
        self._check_expectation()
        return self

    def _check_expectation(self) -> None:
        direction = _PRESSING_DIRECTION.get(self.kind)
        if direction is not None:
            if (self.expected_metric, self.expected_direction) != ("pressing_intensity", direction):
                raise ValueError(f"a {self.kind} expects pressing_intensity to go {direction}")
        elif self.kind != "tactical_shift" and self.expected_metric is not None:
            raise ValueError(f"a {self.kind} storyline expects no metric to move")


class GroundTruth(WireModel):
    """Every storyline of one simulated match, in the order they happened."""

    match_id: MatchId
    seed: Annotated[int, Field(ge=0)]
    storyline: Label
    home: ClubCode
    away: ClubCode
    # The result once every correction has been applied.
    final_score: Score
    storylines: Annotated[
        tuple[StorylineTruth, ...], Field(max_length=MAX_STORYLINES, strict=False)
    ]

    @model_validator(mode="after")
    def _storylines_belong_to_the_match(self) -> "GroundTruth":
        if self.home == self.away:
            raise ValueError("home and away clubs must differ")
        for item in self.storylines:
            if item.club not in {self.home, self.away}:
                raise ValueError(f"club {item.club} is not in the match")
            for event_id in item.event_ids:
                if match_of(event_id) != self.match_id:
                    raise ValueError(f"event {event_id} belongs to match {match_of(event_id)}")
        return self


GROUND_TRUTH_ADAPTER: TypeAdapter[GroundTruth] = TypeAdapter(GroundTruth)


def parse_ground_truth(raw: object) -> GroundTruth:
    """Validate decoded wire data (camelCase keys only) into ground truth."""
    return GROUND_TRUTH_ADAPTER.validate_python(raw, by_alias=True, by_name=False)


def parse_ground_truth_json(data: str | bytes) -> GroundTruth:
    """Validate JSON text into ground truth."""
    return GROUND_TRUTH_ADAPTER.validate_json(data, by_alias=True, by_name=False)
