"""The time-bound promise, proved: under any live position, every answer equals the answer
computed from only the events published by then."""

from functools import cache
from typing import get_args

import pytest

from fourth_official_contracts import MetricName
from fourth_official_match_data import demo_store, tools
from fourth_official_match_data.store import InMemoryStore
from fourth_official_moments.detector import detect
from fourth_official_stats.prepare import prepare
from fourth_official_stats.snapshots import SnapshotKey, snapshot

LIVE_POSITIONS = (150, 700, 1450, 1705, 2100)
METRICS: tuple[MetricName, ...] = get_args(MetricName)


@cache
def store() -> InMemoryStore:
    return demo_store()


@pytest.mark.parametrize("live", LIVE_POSITIONS)
def test_snapshots_and_moments_are_what_the_published_events_alone_give(live: int) -> None:
    record = store().record("m42")
    published = prepare(record.match.context, [e for e in record.match.events if e.seq <= live])
    bounded = store().with_live_seq("m42", live)

    for metric in METRICS:
        scope = "match" if metric == "control_chaos" else "NGT"
        for window in ("5m", "15m", "match"):
            served = tools.get_metric(bounded, "m42", metric=metric, scope=scope, window=window)
            alone = snapshot(published, as_of_seq=live, key=SnapshotKey(metric, scope, window))
            assert served == alone, (metric, window)
    assert tools.list_moments(bounded, "m42").moments == detect(published)[1]
