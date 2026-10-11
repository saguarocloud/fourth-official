# fourth-official-stats

Deterministic stats engine: every metric returns its value and the event IDs it came from. Definitions in [docs/metrics.md](../../docs/metrics.md).

```python
from fourth_official_stats.context import MatchContext
from fourth_official_stats.snapshots import SnapshotKey, snapshot, snapshots_at

context = MatchContext(match_id="m42", home="HCY", away="NGT")
one = snapshot(context, events, as_of_seq=187, key=SnapshotKey("possession", "HCY", "5m"))
every = snapshots_at(context, events, as_of_seq=187)  # 63 snapshots: 21 keys x 3 windows
```
