"""Operations in the API: the matchday's current run measured against its objectives, computed
from each match's feed and the times its log noted. Public and read-only, like the feeds it is
computed from: counts and durations, nothing else.

Measures live as long as the process: a restart (or the API scaling to zero) starts them afresh
with the next run, as the feeds do (docs/cost-model.md).
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response

from fourth_official_policy.book import PolicyBook
from fourth_official_replay import Matchday
from fourth_official_replay.operations import measure, report

NO_STORE = {"Cache-Control": "no-store"}
# A report is reused this long, so a burst of requests computes it once.
FRESH_SECONDS = 2.0


def _compute(matchday: Matchday, book: PolicyBook) -> dict[str, Any]:
    budgets = {tenant: book.current(tenant).latency_budget_ms for tenant in book.tenants()}
    statuses = matchday.status()
    # The matches of a run share the infrastructure (docs/cost-model.md).
    sharing = sum(status.state != "idle" for status in statuses)
    measured = []
    for status in statuses:
        feed = matchday.feed(status.match_id)
        entries, timing = feed.snapshot()
        measured.append(
            measure(
                status.match_id,
                status.state,
                entries,
                timing,
                now=feed.now(),
                sharing=sharing,
                budgets=budgets,
            )
        )
    return report(measured, generated_at=datetime.now(UTC)).to_wire()


def operations_router(clock: Callable[[], float] = time.monotonic) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["operations"])
    cached: dict[str, tuple[float, dict[str, Any]]] = {}

    # Async, so the feeds are read on the event loop that writes them, never from a thread.
    @router.get("/operations")
    async def operations(request: Request, response: Response) -> dict[str, Any]:
        now = clock()
        last = cached.get("report")
        if last is None or now - last[0] >= FRESH_SECONDS:
            last = (now, _compute(request.app.state.matchday, request.app.state.policies))
            cached["report"] = last
        response.headers.update(NO_STORE)
        return last[1]

    return router
