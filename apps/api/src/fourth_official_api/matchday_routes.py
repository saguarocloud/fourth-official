"""The matchday API: list the matches, start the replay, read or stream each match's feed.

Feed entries are the wire contract (`FeedEntry`): insight entries carry text already rendered by
code, so clients show them as plain text. Every run of the matchday is a new generation of each
feed; stream event IDs are `generation:entrySeq`, so a client resuming from another run starts
over instead of skipping entries.
"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Path, Query, Request, Response
from fastapi.responses import StreamingResponse

from fourth_official_contracts import WireModel
from fourth_official_replay import FeedLog, Matchday, MatchdayBusyError

# A reader with nothing new still hears from the server this often, so proxies keep it open.
HEARTBEAT_SECONDS = 15.0
# A stream ends after this long; clients reconnect with Last-Event-ID and lose nothing.
STREAM_LIFETIME_SECONDS = 30 * 60.0
MAX_STREAMS = 200
MAX_ENTRIES_PER_PAGE = 1000
# Starting a run spends model tokens: callers must say who they are, which a cross-site form
# cannot do without a CORS preflight this API never grants.
START_HEADER = "X-Requested-By"
START_HEADER_VALUE = "fourth-official"
MatchIdParam = Annotated[str, Path(pattern=r"^m[0-9]{1,12}$")]


class MatchSummary(WireModel):
    match_id: str
    home: str
    away: str
    home_name: str
    away_name: str
    state: str
    entries: int


def _matchday(request: Request) -> Matchday:
    matchday: Matchday = request.app.state.matchday
    return matchday


def _feed(matchday: Matchday, match_id: str) -> FeedLog:
    try:
        return matchday.feed(match_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown match") from None


def resume_point(last_event_id: str | None, generation: int) -> int:
    """Where a reconnecting client resumes: after its last entry if it is from the current run,
    otherwise from the top. Anything unreadable also starts from the top."""
    gen, _, seq = (last_event_id or "").partition(":")
    if not (gen.isdigit() and seq.isdigit()) or int(gen) != generation:
        return 0
    return min(int(seq), 1_000_000)


async def events(
    feed: FeedLog, generation: int, after: int, *, lifetime: float = STREAM_LIFETIME_SECONDS
) -> AsyncGenerator[str]:
    """Server-sent events for the feed after `after`, with heartbeats, until the run is finished
    or the stream's lifetime runs out. A new run is announced with a `reset` event."""
    deadline = time.monotonic() + lifetime
    while time.monotonic() < deadline:
        view = await feed.wait_beyond(generation, after, timeout=HEARTBEAT_SECONDS)
        if view.generation != generation:
            generation, after = view.generation, 0
            yield f"event: reset\ndata: {json.dumps({'generation': generation})}\n\n"
            continue
        for entry in view.entries:
            data = json.dumps(entry.to_wire(), separators=(",", ":"))
            yield f"id: {generation}:{entry.entry_seq}\nevent: {entry.kind}\ndata: {data}\n\n"
            after = entry.entry_seq
        if view.finished and after >= len(feed.entries):
            return
        if not view.entries:
            yield ": keep-alive\n\n"


def matchday_router(
    summaries: dict[str, dict[str, str]], *, allowed_origins: frozenset[str] = frozenset()
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["matchday"])
    streams = asyncio.Semaphore(MAX_STREAMS)

    @router.get("/matches")
    def matches(request: Request, response: Response) -> dict[str, list[dict[str, Any]]]:
        response.headers["Cache-Control"] = "no-store"
        return {
            "matches": [
                MatchSummary(
                    match_id=status.match_id,
                    state=status.state,
                    entries=status.entries,
                    **summaries[status.match_id],
                ).to_wire()
                for status in _matchday(request).status()
            ]
        }

    @router.post("/matchday", status_code=202)
    async def start(
        request: Request,
        response: Response,
        requested_by: Annotated[str | None, Header(alias=START_HEADER)] = None,
        origin: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        response.headers["Cache-Control"] = "no-store"
        if requested_by != START_HEADER_VALUE or (origin and origin not in allowed_origins):
            raise HTTPException(
                status_code=403,
                detail="the matchday is started from the studio",
                headers={"Cache-Control": "no-store"},
            )
        try:
            await _matchday(request).start()
        except MatchdayBusyError as busy:
            raise HTTPException(
                status_code=409, detail=str(busy), headers={"Cache-Control": "no-store"}
            ) from None
        return {"status": "started"}

    @router.get("/matches/{match_id}/feed")
    def feed(
        match_id: MatchIdParam,
        request: Request,
        response: Response,
        after: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    ) -> dict[str, Any]:
        view = _feed(_matchday(request), match_id).view(after)
        response.headers["Cache-Control"] = "no-store"
        page = view.entries[:MAX_ENTRIES_PER_PAGE]
        more = len(page) < len(view.entries)
        return {
            "generation": view.generation,
            "entries": [e.to_wire() for e in page],
            "hasMore": more,
            "finished": view.finished and not more,
        }

    @router.get("/matches/{match_id}/stream")
    async def stream(
        match_id: MatchIdParam,
        request: Request,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        log = _feed(_matchday(request), match_id)
        if streams.locked():
            raise HTTPException(status_code=503, detail="too many open streams; try again soon")
        await streams.acquire()

        async def limited() -> AsyncGenerator[str]:
            try:
                generation = log.generation
                async for chunk in events(log, generation, resume_point(last_event_id, generation)):
                    yield chunk
            finally:
                streams.release()

        return StreamingResponse(
            limited(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return router
