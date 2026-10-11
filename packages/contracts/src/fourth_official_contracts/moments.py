"""Moments: something in the match worth explaining (stage three, Explain).

A deterministic Moment Detector finds them from events and metric snapshots, never a model. Each
moment cites exactly the events and snapshots that show it, so the Analyst's explanation and the
Verifier's checks start from the same evidence.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.metrics import (
    MetricName,
    SnapshotId,
    snapshot_id_parts,
)
from fourth_official_contracts.primitives import (
    ClubCode,
    EventId,
    MatchClock,
    MatchId,
    Seq,
    WireModel,
    match_of,
)

MomentKind = Literal[
    "goal",
    "big_chance",
    "red_card",
    "var_overturn",
    "pressing_collapse",
    "pressing_surge",
    "momentum_swing",
    "tactical_shift",
]
# Moments shown by events, and moments shown by a metric moving.
EVENT_MOMENTS: frozenset[str] = frozenset({"goal", "big_chance", "red_card", "var_overturn"})
SHIFT_MOMENTS: frozenset[str] = frozenset(
    {"pressing_collapse", "pressing_surge", "momentum_swing", "tactical_shift"}
)
MomentId = Annotated[
    str,
    StringConstraints(
        max_length=64, pattern=r"^mo-m[0-9]{1,12}-[a-z_]{2,24}-[A-Z]{3}-s[0-9]{4,9}$"
    ),
]
MAX_MOMENT_EVENTS = 64
MAX_MOMENT_SNAPSHOTS = 16


def moment_id_for(match_id: str, *, kind: str, club: str, as_of_seq: int) -> str:
    """The canonical identity of a moment: every part names a field of the moment."""
    return f"mo-{match_id}-{kind}-{club}-s{as_of_seq:04d}"


# A pressing story is told by pressing_intensity, moving the way its name says.
_PRESSING_DIRECTION = {"pressing_collapse": "down", "pressing_surge": "up"}


class MetricShift(WireModel):
    """A metric that moved: its value in a baseline snapshot and in the current one."""

    metric: MetricName
    before: float
    after: float
    before_snapshot_id: SnapshotId
    after_snapshot_id: SnapshotId

    @model_validator(mode="after")
    def _snapshots_measure_the_metric(self) -> "MetricShift":
        if self.before_snapshot_id == self.after_snapshot_id:
            raise ValueError("before and after snapshots must differ")
        before = snapshot_id_parts(self.before_snapshot_id)
        after = snapshot_id_parts(self.after_snapshot_id)
        for parts, snapshot_id in (
            (before, self.before_snapshot_id),
            (after, self.after_snapshot_id),
        ):
            if parts.metric != self.metric:
                raise ValueError(f"snapshot {snapshot_id} measures another metric")
        if (before.match_id, before.scope) != (after.match_id, after.scope):
            raise ValueError("before and after snapshots must be about the same match and scope")
        if before.as_of_seq >= after.as_of_seq:
            raise ValueError("the before snapshot must be taken before the after snapshot")
        return self


class Moment(WireModel):
    moment_id: MomentId
    match_id: MatchId
    kind: MomentKind
    # The club the moment is about: the scorer's side, the side sent a player off, the side whose
    # press collapsed, the side momentum swung towards.
    club: ClubCode
    # The last event the detector could see when it found the moment.
    as_of_seq: Seq
    clock: MatchClock
    event_ids: Annotated[tuple[EventId, ...], Field(max_length=MAX_MOMENT_EVENTS, strict=False)]
    metric_snapshot_ids: Annotated[
        tuple[SnapshotId, ...], Field(max_length=MAX_MOMENT_SNAPSHOTS, strict=False)
    ]
    shifts: Annotated[tuple[MetricShift, ...], Field(max_length=4, strict=False)]

    @model_validator(mode="after")
    def _identity_and_evidence_are_consistent(self) -> "Moment":
        expected = moment_id_for(
            self.match_id, kind=self.kind, club=self.club, as_of_seq=self.as_of_seq
        )
        if self.moment_id != expected:
            raise ValueError(f"moment id {self.moment_id} does not name this moment")
        self._check_events()
        self._check_snapshots()
        return self

    def _check_events(self) -> None:
        if self.kind in EVENT_MOMENTS and not self.event_ids:
            raise ValueError(f"a {self.kind} moment needs the events that show it")
        if self.kind in SHIFT_MOMENTS and self.event_ids:
            raise ValueError(f"a {self.kind} moment is shown by metrics; it cites no events")
        if any(match_of(e) != self.match_id for e in self.event_ids):
            raise ValueError("an event cited belongs to another match")
        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError("events must be cited once each")

    def _check_snapshots(self) -> None:
        if self.kind in SHIFT_MOMENTS and not self.shifts:
            raise ValueError(f"a {self.kind} moment needs the metric shift that shows it")
        if self.kind in EVENT_MOMENTS and self.shifts:
            raise ValueError(f"a {self.kind} moment is shown by events; it carries no metric shift")
        if len(set(self.metric_snapshot_ids)) != len(self.metric_snapshot_ids):
            raise ValueError("snapshots must be cited once each (unique)")
        in_shifts = [i for s in self.shifts for i in (s.before_snapshot_id, s.after_snapshot_id)]
        if sorted(in_shifts) != sorted(self.metric_snapshot_ids):
            raise ValueError("a moment cites exactly the snapshots of its shifts")
        for snapshot_id in self.metric_snapshot_ids:
            parts = snapshot_id_parts(snapshot_id)
            if parts.match_id != self.match_id:
                raise ValueError("a snapshot cited belongs to another match")
            if parts.scope not in {self.club, "match"}:
                raise ValueError(f"snapshot {snapshot_id} is not about {self.club}")
            if parts.as_of_seq > self.as_of_seq:
                raise ValueError(f"snapshot {snapshot_id} is after the moment")
        direction = _PRESSING_DIRECTION.get(self.kind)
        for shift in self.shifts if direction else ():
            if shift.metric != "pressing_intensity":
                raise ValueError(f"a {self.kind} is shown by pressing_intensity")
            moved = "down" if shift.after < shift.before else "up"
            if moved != direction or shift.after == shift.before:
                raise ValueError(f"in a {self.kind}, pressing_intensity must go {direction}")


# The model's own config already hides input in validation errors.
MOMENT_ADAPTER: TypeAdapter[Moment] = TypeAdapter(Moment)


def parse_moment(raw: object) -> Moment:
    """Validate decoded wire data (camelCase keys only) into a moment."""
    return MOMENT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)


def parse_moment_json(data: str | bytes) -> Moment:
    """Validate JSON text into a moment."""
    return MOMENT_ADAPTER.validate_json(data, by_alias=True, by_name=False)
