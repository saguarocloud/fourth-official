"""Metric snapshots: numbers computed by the stats engine (stage two, Interpret).

Every snapshot records the exact events it was computed from, so any claim that cites it can be
traced back to the match data. When a correction changes those events, the metric is recomputed
and published as a new version that supersedes the old one; the old snapshot is kept.
"""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from fourth_official_contracts.primitives import (
    EventId,
    MatchClock,
    MatchId,
    Seq,
    Version,
    WireModel,
    match_of,
)

MetricName = Literal[
    "possession",
    "field_tilt",
    "passes",
    "pass_completion",
    "shots",
    "shots_on_target",
    "xg",
    "ppda",
    "pressing_intensity",
    "momentum",
    "control_chaos",
]
MetricWindow = Literal["5m", "15m", "match"]
# Metrics measured for the whole match rather than per club.
MATCH_WIDE_METRICS: frozenset[str] = frozenset({"control_chaos"})
SnapshotId = Annotated[
    str,
    StringConstraints(
        max_length=96,
        pattern=r"^ms-m[0-9]{1,12}-[a-z_]{2,24}-([A-Z]{3}|match)-(5m|15m|match)-s[0-9]{4,9}-v[0-9]{1,4}$",
    ),
]
# A metric is about one club, or the whole match.
Scope = Annotated[str, StringConstraints(pattern=r"^([A-Z]{3}|match)$")]
# The stats engine refuses matches with more events than this, so evidence never exceeds it.
MAX_INPUTS = 5_000


def snapshot_id_for(
    match_id: str, *, metric: str, scope: str, window: str, as_of_seq: int, version: int
) -> str:
    """The canonical identity of a snapshot: every part names a field of the snapshot."""
    return f"ms-{match_id}-{metric}-{scope}-{window}-s{as_of_seq:04d}-v{version}"


def _event_number(event_id: str) -> int:
    return int(event_id.rsplit("-e", 1)[1])


class MetricSnapshot(WireModel):
    snapshot_id: SnapshotId
    match_id: MatchId
    metric: MetricName
    scope: Scope
    window: MetricWindow
    as_of: MatchClock
    # The last event the computation could see.
    as_of_seq: Seq
    # None when the metric is undefined (for example PPDA with no defensive actions).
    value: float | None
    # A JSON array arrives as a list; it is stored as an immutable tuple (elements stay strict).
    inputs: Annotated[tuple[EventId, ...], Field(max_length=MAX_INPUTS, strict=False)]
    version: Version
    supersedes: SnapshotId | None

    def _id(self, version: int) -> str:
        return snapshot_id_for(
            self.match_id,
            metric=self.metric,
            scope=self.scope,
            window=self.window,
            as_of_seq=self.as_of_seq,
            version=version,
        )

    @model_validator(mode="after")
    def _identity_evidence_and_lineage_are_consistent(self) -> "MetricSnapshot":
        if self.snapshot_id != self._id(self.version):
            raise ValueError(f"snapshot id {self.snapshot_id} does not name this snapshot")
        if (self.metric in MATCH_WIDE_METRICS) != (self.scope == "match"):
            raise ValueError(f"metric {self.metric} cannot have scope {self.scope}")
        foreign = [i for i in self.inputs if match_of(i) != self.match_id]
        if foreign:
            raise ValueError(f"inputs {foreign[:3]} belong to another match")
        numbers = [_event_number(i) for i in self.inputs]
        if numbers != sorted(set(numbers)):
            raise ValueError("evidence must list each event once, in match order")
        expected = None if self.version == 1 else self._id(self.version - 1)
        if self.supersedes != expected:
            raise ValueError(
                "a first version supersedes nothing; a restatement supersedes the same snapshot "
                "at the previous version"
            )
        return self


# The model's own config already hides input in validation errors.
METRIC_SNAPSHOT_ADAPTER: TypeAdapter[MetricSnapshot] = TypeAdapter(MetricSnapshot)


def parse_metric_snapshot(raw: object) -> MetricSnapshot:
    """Validate decoded wire data (camelCase keys) into a metric snapshot."""
    return METRIC_SNAPSHOT_ADAPTER.validate_python(raw, by_alias=True, by_name=False)
