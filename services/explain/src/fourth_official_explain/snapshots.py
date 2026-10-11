"""Snapshots by ID, computed on demand from the match: whatever the Match Data tools served.

This is a lookup, not a mapping: snapshots are computed when asked for, so there is nothing to
list, and two lookups are equal only if they are the same object.
"""

from fourth_official_contracts import MetricSnapshot, snapshot_id_parts
from fourth_official_stats.prepare import PreparedMatch
from fourth_official_stats.snapshots import SnapshotKey, snapshot


class ComputedSnapshots:
    """Every first-version snapshot of one match, by ID. An ID that names another match, a
    restated version, an unknown metric or a seq with no event is simply absent."""

    def __init__(self, match: PreparedMatch) -> None:
        self._match = match

    def get(self, snapshot_id: str, /) -> MetricSnapshot | None:
        try:
            parts = snapshot_id_parts(snapshot_id)
            if parts.match_id != self._match.context.match_id or parts.version != 1:
                return None
            key = SnapshotKey(parts.metric, parts.scope, parts.window)  # type: ignore[arg-type]
            found = snapshot(self._match, as_of_seq=parts.as_of_seq, key=key)
        except (ValueError, KeyError):  # an unknown metric, scope or window, or no such moment
            return None
        return found if found.snapshot_id == snapshot_id else None

    def __contains__(self, snapshot_id: object) -> bool:
        return isinstance(snapshot_id, str) and self.get(snapshot_id) is not None
