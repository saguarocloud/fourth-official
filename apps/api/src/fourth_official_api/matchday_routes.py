"""The matchday API: list the matches, start the replay, read or stream each match's feed.

Feed entries are the wire contract (`FeedEntry`): insight entries carry text already rendered by
code, so clients show them as plain text.
"""

import json
from collections.abc import AsyncGenerator, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Path, Query, Response
from fastapi.responses import StreamingResponse

from fourth_official_contracts import WireModel
from fourth_official_replay import FeedLog, Matchday, MatchdayBusyError

# A reader with nothing new still hears from the server this often, so proxies keep it open.
HEARTBEAT_SECONDS = 15.0
MAX_ENTRIES_PER_PAGE = 1000
MatchIdParam = Annotated[str, Path(pattern=r"^m[0-9]{1,12}$")]


class MatchSummary(WireModel):
    match_id: str
    home: str
    away: str
    home_name: str
    away_name: str
    state: str
    entries: int


def _feed(matchday: Matchday, match_id: str) -> FeedLog:
    try:
        return matchday.feed(match_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown match") from None


async def events(feed: FeedLog, after: int) -> AsyncGenerator[str]:
    """Server-sent events for the feed after `after`, with heartbeats, until it is finished."""
    while True:
        entries = await feed.wait_beyond(after, timeout=HEARTBEAT_SECONDS)
        for entry in entries:
            data = json.dumps(entry.to_wire(), separators=(",", ":"))
            yield f"id: {entry.entry_seq}\nevent: {entry.kind}\ndata: {data}\n\n"
            after = entry.entry_seq
        if feed.finished and after >= len(feed.entries):
            return
        if not entries:
            yield ": keep-alive\n\n"


def matchday_router(
    current: Callable[[], Matchday], summaries: dict[str, dict[str, str]]
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["matchday"])

    @router.get("/matches")
    def matches(response: Response) -> dict[str, list[dict[str, Any]]]:
        response.headers["Cache-Control"] = "no-store"
        return {
            "matches": [
                MatchSummary(
                    match_id=status.match_id,
                    state=status.state,
                    entries=status.entries,
                    **summaries[status.match_id],
                ).to_wire()
                for status in current().status()
            ]
        }

    @router.post("/matchday", status_code=202)
    async def start() -> dict[str, str]:
        try:
            await current().start()
        except MatchdayBusyError as busy:
            raise HTTPException(status_code=409, detail=str(busy)) from None
        return {"status": "started"}

    @router.get("/matches/{match_id}/feed")
    def feed(
        match_id: MatchIdParam,
        response: Response,
        after: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    ) -> dict[str, Any]:
        log = _feed(current(), match_id)
        response.headers["Cache-Control"] = "no-store"
        entries = log.since(after)[:MAX_ENTRIES_PER_PAGE]
        return {"entries": [e.to_wire() for e in entries], "finished": log.finished}

    @router.get("/matches/{match_id}/stream")
    def stream(
        match_id: MatchIdParam,
        last_event_id: Annotated[int, Header(ge=0, le=1_000_000)] = 0,
    ) -> StreamingResponse:
        log = _feed(current(), match_id)
        return StreamingResponse(
            events(log, last_event_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return router
