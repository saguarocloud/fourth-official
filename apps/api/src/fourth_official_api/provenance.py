"""Provenance in the API: every narrative partner item is issued a signed record as its match's
feed publishes it (and re-issued when its state changes or a correction reaches it), and anyone
can read a record and check it was not changed since (ADR-013).

Records are public by design, as the Verify page is: they carry no more than the partner feeds do.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Request, Response

from fourth_official_contracts import (
    CorrectionReportEntry,
    FeedEntry,
    InsightEntry,
    TenantItemEntry,
)
from fourth_official_provenance import (
    ProvenanceStore,
    Signer,
    record_for,
    sign_record,
    verify_signed,
)
from fourth_official_provenance.azure import UnreadableRecordError
from fourth_official_replay import FeedLog

logger = logging.getLogger(__name__)
ItemIdParam = Annotated[
    str, Path(max_length=128, pattern=r"^it-[a-z]+(-[a-z]+)*-[A-Za-z0-9_-]{1,100}$")
]
NO_STORE = {"Cache-Control": "no-store"}
# How often a finished feed is checked for a new run.
IDLE_SECONDS = 2.0


def _now() -> datetime:
    # To the millisecond, as the wire writes times: the record signed is the record read back.
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


class Issuer:
    """Follows match feeds and keeps a signed record of every narrative partner item's latest
    version in the store."""

    def __init__(
        self, signer: Signer, store: ProvenanceStore, *, clock: Callable[[], datetime] = _now
    ) -> None:
        self.signer, self.store, self._clock = signer, store, clock
        self._seen: dict[str, tuple[int, int]] = {}

    def caught_up(self, feed: FeedLog) -> bool:
        """Whether every entry of the feed's current run has been dealt with."""
        return self._seen.get(feed.match_id) == (feed.generation, len(feed.entries))

    async def follow(self, feed: FeedLog) -> None:
        generation, after = feed.generation, 0
        while True:
            view = await feed.wait_beyond(generation, after, timeout=30.0)
            if view.generation != generation:
                generation, after = view.generation, 0
            entries = feed.entries
            for entry in view.entries:
                after = entry.entry_seq
                await self._issue_for(entry, entries)
            self._seen[feed.match_id] = (generation, after)
            if view.finished and not view.entries:
                await asyncio.sleep(IDLE_SECONDS)

    async def _issue_for(self, entry: FeedEntry, entries: Sequence[FeedEntry]) -> None:
        if isinstance(entry, TenantItemEntry):
            await self._issue(entry, entries)
        elif isinstance(entry, CorrectionReportEntry):
            # A correction reached these items: their records now name it.
            for action in entry.actions:
                latest = _latest(entries, action.item_id)
                if latest is not None:
                    await self._issue(latest, entries)

    async def _issue(self, item: TenantItemEntry, entries: Sequence[FeedEntry]) -> None:
        insight_id = item.localized.insight_id if item.localized else None
        canonical = next(
            (
                e
                for e in entries
                if isinstance(e, InsightEntry) and e.insight.insight_id == insight_id
            ),
            None,
        )
        corrections = sorted(
            {
                e.correction_id
                for e in entries
                if isinstance(e, CorrectionReportEntry)
                and any(a.item_id == item.overlay.item_id for a in e.actions)
            }
        )
        record = record_for(item, canonical, issued_at=self._clock(), corrections=corrections)
        if record is None:
            return
        try:
            await self.store.put(await sign_record(record, self.signer))
        except Exception:
            # One record not issued is logged; the next item is not held up by it.
            logger.exception("could not issue provenance for %s", record.item_id)


def _latest(entries: Sequence[FeedEntry], item_id: str) -> TenantItemEntry | None:
    for entry in reversed(entries):
        if isinstance(entry, TenantItemEntry) and entry.overlay.item_id == item_id:
            return entry
    return None


def provenance_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["provenance"])

    @router.get("/items/{item_id}/provenance")
    async def provenance(
        item_id: ItemIdParam, request: Request, response: Response
    ) -> dict[str, Any]:
        response.headers.update(NO_STORE)
        issuer: Issuer = request.app.state.provenance
        try:
            signed = await issuer.store.get(item_id)
        except UnreadableRecordError:
            return {
                "provenance": None,
                "verification": {"valid": False, "reason": "the stored record no longer reads"},
            }
        if signed is None:
            raise HTTPException(
                status_code=404,
                detail="no provenance for this item: it is not on a feed, or no agent wrote it",
                headers=NO_STORE,
            )
        verdict = await verify_signed(signed, issuer.signer)
        return {
            "provenance": signed.to_wire(),
            "verification": {"valid": verdict.valid, "reason": verdict.reason},
        }

    return router
