"""Provenance in the API: every narrative partner item is issued a signed record as its match's
feed publishes it (and re-issued when its state changes or a correction reaches it), and anyone
can read a record and check it (ADR-013).

Records are public by design, as the Verify page is: they carry no more than the partner feeds do.
Reading checks more than the signature: the record must be of the item asked for, and the latest
issued for it, so a genuine record moved to another item or an earlier issue restored over a later
one does not pass.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any

from azure.core.exceptions import AzureError
from fastapi import APIRouter, HTTPException, Path, Request, Response

from fourth_official_contracts import (
    CorrectionReportEntry,
    FeedEntry,
    InsightEntry,
    SignedProvenance,
    TenantItemEntry,
)
from fourth_official_provenance import (
    ProvenanceStore,
    Signer,
    UnreadableRecordError,
    record_for,
    sign_record,
    verify_signed,
)
from fourth_official_replay import FeedLog

logger = logging.getLogger(__name__)
ItemIdParam = Annotated[
    str, Path(max_length=128, pattern=r"^it-[a-z]+(-[a-z]+)*-[A-Za-z0-9_-]{1,100}$")
]
NO_STORE = {"Cache-Control": "no-store"}
# How often a finished feed is checked for a new run, and a crashed follower restarts.
IDLE_SECONDS = 2.0
# Waits between tries at signing and storing one record.
BACKOFF = (0.2, 1.0, 3.0)
# Reads per caller per minute. The web app's proxy limits each visitor (60 a minute) and reaches
# the API as one caller, so this is a ceiling on any single caller, the web app included.
READS_PER_MINUTE = 600
# Verdicts kept for records read again unchanged, so a read is not a vault call each time.
CACHED_VERDICTS = 4096


def _now() -> datetime:
    # To the millisecond, as the wire writes times: the record signed is the record read back.
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


class Issuer:
    """Follows match feeds and keeps a signed record of every narrative partner item's latest
    version in the store, remembering the latest issue of each."""

    def __init__(
        self,
        signer: Signer,
        store: ProvenanceStore,
        *,
        clock: Callable[[], datetime] = _now,
        backoff: Sequence[float] = BACKOFF,
    ) -> None:
        self.signer, self.store, self._clock, self._backoff = signer, store, clock, tuple(backoff)
        self._seen: dict[str, tuple[int, int]] = {}
        # The content hash of each item's latest issue: what a read is checked against.
        self.latest: dict[str, str] = {}
        # Items whose latest version could not be issued yet; retried as the feed is followed.
        self.failing: set[str] = set()

    def caught_up(self, feed: FeedLog) -> bool:
        """Whether every entry of the feed's current run has been issued."""
        return self._seen.get(feed.match_id) == (feed.generation, len(feed.entries)) and not any(
            item_id in self.failing for item_id in _item_ids(feed.entries)
        )

    async def follow(self, feed: FeedLog) -> None:
        """Issue records for the feed for as long as it runs; an unexpected failure is logged and
        following starts again, so one bad entry never ends the match's records."""
        while True:
            try:
                await self._follow(feed)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("provenance stopped following %s; starting again", feed.match_id)
                await asyncio.sleep(IDLE_SECONDS)

    async def _follow(self, feed: FeedLog) -> None:
        generation, after = feed.generation, 0
        while True:
            view = await feed.wait_beyond(generation, after, timeout=30.0)
            if view.generation != generation:
                generation, after = view.generation, 0
            entries = feed.entries
            for entry in view.entries:
                if feed.generation != generation:
                    break  # a new run started: its entries come next, the old ones are moot
                after = entry.entry_seq
                await self._issue_for(entry, entries)
            await self._retry(entries)
            self._seen[feed.match_id] = (generation, after)
            if view.finished and not view.entries:
                await asyncio.sleep(IDLE_SECONDS)

    async def _retry(self, entries: Sequence[FeedEntry]) -> None:
        for item_id in _item_ids(entries) & self.failing:
            latest = _latest(entries, item_id)
            if latest is not None:
                await self.issue(latest, entries, True)

    async def _issue_for(self, entry: FeedEntry, entries: Sequence[FeedEntry]) -> None:
        if isinstance(entry, TenantItemEntry):
            await self.issue(entry, entries, True)
        elif isinstance(entry, CorrectionReportEntry):
            # A correction reached these items: their records now name it.
            for action in entry.actions:
                latest = _latest(entries, action.item_id)
                if latest is not None:
                    await self.issue(latest, entries, True)

    async def issue(
        self, item: TenantItemEntry, entries: Sequence[FeedEntry], store: bool
    ) -> SignedProvenance | None:
        """Sign (and, with `store`, keep) the record of the item as it stands; None for a graphic
        no agent wrote, or when it could not be issued (it is then retried)."""
        try:
            record = record_for(
                item,
                _canonical(entries, item),
                issued_at=self._clock(),
                corrections=_corrections(entries, item.overlay.item_id),
            )
        except ValueError:
            logger.exception("no valid record for %s", item.overlay.item_id)
            return None
        if record is None:
            return None
        for wait in (*self._backoff, None):
            try:
                signed = await sign_record(record, self.signer)
                if store:
                    await self.store.put(signed)
                    self.latest[record.item_id] = signed.content_hash
                    self.failing.discard(record.item_id)
                return signed
            except Exception:
                if wait is None:
                    logger.exception("could not issue provenance for %s", record.item_id)
                    self.failing.add(record.item_id)
                    return None
                await asyncio.sleep(wait)
        return None  # pragma: no cover - the loop always returns


def _item_ids(entries: Sequence[FeedEntry]) -> set[str]:
    return {e.overlay.item_id for e in entries if isinstance(e, TenantItemEntry)}


def _canonical(entries: Sequence[FeedEntry], item: TenantItemEntry) -> InsightEntry | None:
    insight_id = item.localized.insight_id if item.localized else None
    return next(
        (e for e in entries if isinstance(e, InsightEntry) and e.insight.insight_id == insight_id),
        None,
    )


def _corrections(entries: Sequence[FeedEntry], item_id: str) -> list[str]:
    return sorted(
        {
            e.correction_id
            for e in entries
            if isinstance(e, CorrectionReportEntry) and any(a.item_id == item_id for a in e.actions)
        }
    )


def _latest(entries: Sequence[FeedEntry], item_id: str) -> TenantItemEntry | None:
    for entry in reversed(entries):
        if isinstance(entry, TenantItemEntry) and entry.overlay.item_id == item_id:
            return entry
    return None


def _client(request: Request) -> str:
    """The address the ingress appended (the last X-Forwarded-For entry); earlier entries are the
    client's own claim, never trusted."""
    forwarded = request.headers.get("x-forwarded-for", "")
    last = forwarded.split(",")[-1].strip()
    return last or (request.client.host if request.client else "direct")


class _Reads:
    """A fixed one-minute window of reads per client, in memory."""

    def __init__(self, per_minute: int) -> None:
        self._per_minute = per_minute
        self._windows: dict[str, tuple[float, int]] = {}

    def take(self, client: str) -> int:
        """0 when allowed, else the seconds to wait."""
        now = time.monotonic()
        self._windows = {k: w for k, w in self._windows.items() if now - w[0] < 60}
        start, used = self._windows.get(client, (now, 0))
        if used >= self._per_minute:
            return max(1, int(60 - (now - start)))
        self._windows[client] = (start, used + 1)
        return 0


def provenance_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["provenance"])
    reads = _Reads(READS_PER_MINUTE)
    verdicts: OrderedDict[tuple[str, str, str], tuple[bool, str | None]] = OrderedDict()

    async def verdict_of(signed: SignedProvenance, issuer: Issuer) -> tuple[bool, str | None]:
        key = (signed.record.item_id, signed.content_hash, signed.signature)
        if key not in verdicts:
            try:
                checked = await verify_signed(signed, issuer.signer)
                verdicts[key] = (checked.valid, checked.reason)
            except Exception:
                logger.exception("could not check %s", signed.record.item_id)
                return False, "the signature could not be checked"
            if len(verdicts) > CACHED_VERDICTS:
                verdicts.popitem(last=False)
        return verdicts[key]

    @router.get("/items/{item_id}/provenance")
    async def provenance(
        item_id: ItemIdParam, request: Request, response: Response
    ) -> dict[str, Any]:
        response.headers.update(NO_STORE)
        wait = reads.take(_client(request))
        if wait:
            raise HTTPException(
                status_code=429,
                detail="too many reads from here; try again shortly",
                headers={**NO_STORE, "Retry-After": str(wait)},
            )
        issuer: Issuer = request.app.state.provenance
        try:
            signed = await issuer.store.get(item_id)
        except UnreadableRecordError:
            return _verdict(None, False, "the stored record no longer reads")
        except AzureError:
            # The item id came from the request: it is not written to the log.
            logger.exception("could not read a provenance record from storage")
            raise HTTPException(
                status_code=503, detail="records cannot be read right now", headers=NO_STORE
            ) from None
        if signed is None:
            raise HTTPException(
                status_code=404,
                detail="no provenance for this item: it is not on a feed, or no agent wrote it",
                headers=NO_STORE,
            )
        if signed.record.item_id != item_id:
            return _verdict(signed, False, "the record stored here is of another item")
        latest = issuer.latest.get(item_id)
        if latest is not None and latest != signed.content_hash:
            return _verdict(
                signed, False, "a later issue of this record exists; this one is out of date"
            )
        valid, reason = await verdict_of(signed, issuer)
        return _verdict(signed, valid, reason)

    return router


def _verdict(signed: SignedProvenance | None, valid: bool, reason: str | None) -> dict[str, Any]:
    return {
        "provenance": signed.to_wire() if signed else None,
        "verification": {"valid": valid, "reason": reason},
    }
