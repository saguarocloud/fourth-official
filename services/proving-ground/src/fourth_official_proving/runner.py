"""Run a configuration over benchmark matches: the real pipeline, headless and at full speed.

Each match is replayed exactly as the API replays the demo matchday (moments, the Explainer and
the Verifier, every partner's policy, the corrections desk) with no waiting between events and
fixed clocks. Only the time spent explaining is measured, as that is what a configuration changes.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from functools import partial

from fourth_official_contracts import FeedEntry, GroundTruth, Moment
from fourth_official_explain import Explanation
from fourth_official_match_data import MatchRecord, store_of
from fourth_official_policy import blocked_topics_in, bundled_store
from fourth_official_proving.truth import Truth, truth_of
from fourth_official_replay import FeedLog, Partner, Partners, fixed_clocks, replay
from fourth_official_simulator.engine import MatchSetup, play
from fourth_official_verifier import MatchFacts

Explainer = Callable[[Moment, MatchFacts], Awaitable[Explanation]]
# Matches replayed at once: model calls dominate, and the deployment's rate limit is shared.
CONCURRENCY = 4
MS_PER_SECOND = 1000


@dataclass(frozen=True, slots=True)
class MatchRun:
    """One benchmark match as the pipeline handled it, with what really happened."""

    setup: MatchSetup
    record: MatchRecord
    truth: Truth
    ground_truth: GroundTruth
    entries: tuple[FeedEntry, ...]
    explain_ms: tuple[float, ...]


def partners() -> Partners:
    """Every bundled partner, with its own policy; localised by template (the localizer agent is
    measured separately)."""
    return Partners(
        [
            Partner(policy=p.policy, blocked=partial(blocked_topics_in, policy=p.policy))
            for p in bundled_store().all()
        ],
        localizer=None,
    )


async def _no_wait(seconds: float) -> None:
    return None


async def run_match(
    setup: MatchSetup,
    record: MatchRecord,
    explainer: Explainer,
    *,
    clock: Callable[[], float] = time.perf_counter,
) -> MatchRun:
    timings: list[float] = []

    async def timed(moment: Moment, facts: MatchFacts) -> Explanation:
        start = clock()
        try:
            return await explainer(moment, facts)
        finally:
            timings.append((clock() - start) * MS_PER_SECOND)

    log = FeedLog(setup.match_id)
    await replay(record, log, timed, sleep=_no_wait, partners=partners(), clocks=fixed_clocks())
    played = play(setup)
    return MatchRun(
        setup=setup,
        record=record,
        truth=truth_of(played),
        ground_truth=played.ground_truth,
        entries=tuple(log.entries),
        explain_ms=tuple(timings),
    )


async def run_benchmark(
    setups: Sequence[MatchSetup], explainer: Explainer, *, concurrency: int = CONCURRENCY
) -> tuple[MatchRun, ...]:
    """Every match, `concurrency` at a time, in benchmark order."""
    store = store_of(setups)
    gate = asyncio.Semaphore(concurrency)

    async def one(setup: MatchSetup) -> MatchRun:
        async with gate:
            return await run_match(setup, store.record(setup.match_id), explainer)

    return tuple(await asyncio.gather(*(one(s) for s in setups)))
