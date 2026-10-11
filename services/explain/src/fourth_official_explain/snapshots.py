"""Snapshots by ID, computed on demand from the match: whatever the Match Data tools served."""

from collections.abc import Iterator, Mapping

from fourth_official_contracts import MetricSnapshot, snapshot_id_parts
from fourth_official_stats.prepare import PreparedMatch
from fourth_official_stats.snapshots import SnapshotKey, snapshot


class ComputedSnapshots(Mapping[str, MetricSnapshot]):
    """Every first-version snapshot of one match, by ID. An ID that names another match, a
    restated version, an unknown metric or a seq with no event is simply absent."""

    def __init__(self, match: PreparedMatch) -> None:
        self._match = match

    def __getitem__(self, snapshot_id: str) -> MetricSnapshot:
        try:
            parts = snapshot_id_parts(snapshot_id)
            if parts.match_id != self._match.context.match_id or parts.version != 1:
                raise KeyError(snapshot_id)
            key = SnapshotKey(parts.metric, parts.scope, parts.window)  # type: ignore[arg-type]
            found = snapshot(self._match, as_of_seq=parts.as_of_seq, key=key)
        except (ValueError, KeyError):
            raise KeyError(snapshot_id) from None
        if found.snapshot_id != snapshot_id:
            raise KeyError(snapshot_id)
        return found

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0
