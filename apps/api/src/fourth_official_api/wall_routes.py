"""The Control Room's wall in the API: every match's score, clock, partners on air, items awaiting
an editor and corrections, the latest partner items and the latest correction, computed from the
matchday's feeds. Public and read-only, like the feeds it is computed from.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response

from fourth_official_replay import Matchday
from fourth_official_replay.wall import played_from, wall

NO_STORE = {"Cache-Control": "no-store"}
# A wall is reused this long, so a burst of requests computes it once.
FRESH_SECONDS = 2.0


def _compute(matchday: Matchday) -> dict[str, Any]:
    played = [
        played_from(matchday.record(s.match_id), s.state, matchday.feed(s.match_id))
        for s in matchday.status()
    ]
    return wall(played, generated_at=datetime.now(UTC)).to_wire()


def wall_router(clock: Callable[[], float] = time.monotonic) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["wall"])
    cached: dict[str, tuple[float, dict[str, Any]]] = {}

    # Async, so the feeds are read on the event loop that writes them, never from a thread.
    @router.get("/wall")
    async def matchday_wall(request: Request, response: Response) -> dict[str, Any]:
        now = clock()
        last = cached.get("wall")
        if last is None or now - last[0] >= FRESH_SECONDS:
            last = (now, _compute(request.app.state.matchday))
            cached["wall"] = last
        response.headers.update(NO_STORE)
        return last[1]

    return router
