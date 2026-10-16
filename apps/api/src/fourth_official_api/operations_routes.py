"""Operations in the API: the matchday's current run measured against its objectives, computed
from each match's feed and the times its log noted. Public and read-only, like the feeds it is
computed from: counts and durations, nothing else.

Measures live as long as the process: a restart (or the API scaling to zero) starts them afresh
with the next run, as the feeds do (docs/cost-model.md).
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response

from fourth_official_replay import Matchday
from fourth_official_replay.operations import measure, report

NO_STORE = {"Cache-Control": "no-store"}


def operations_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["operations"])

    @router.get("/operations")
    def operations(request: Request, response: Response) -> dict[str, Any]:
        matchday: Matchday = request.app.state.matchday
        measured = []
        for status in matchday.status():
            feed = matchday.feed(status.match_id)
            measured.append(
                measure(status.match_id, status.state, feed.entries, feed.timing, now=feed.now())
            )
        response.headers.update(NO_STORE)
        return report(measured, generated_at=datetime.now(UTC)).to_wire()

    return router
