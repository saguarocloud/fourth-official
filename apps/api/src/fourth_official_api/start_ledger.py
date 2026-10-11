"""The durable start ledger: when matchday runs started, kept in one blob so the spend guards
(cooldown, daily budget) survive restarts and scale-to-zero.

A start is claimed by reading the starts, checking the guards on them and writing the new start
on condition that the blob is still the version read (an ETag precondition). A start recorded by
any other process in between, such as an overlapping revision during a deploy, makes this one
lose instead of both running.
"""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from azure.core import MatchConditions
from azure.core.exceptions import (
    AzureError,
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import StorageErrorCode
from azure.storage.blob.aio import BlobClient

from fourth_official_replay.matchday import MatchdayBusyError

# Twice the daily budget: enough history for every guard, and the blob never grows.
KEPT_STARTS = 48


class LedgerError(RuntimeError):
    """The ledger cannot be read or written; no start may be recorded until it can."""


class LedgerConflictError(RuntimeError):
    """The blob changed since it was read."""


class Blob(Protocol):
    """One blob, read with its version and written only over the version named."""

    async def read(self) -> tuple[bytes, str] | None: ...

    async def write(self, data: bytes, *, etag: str | None) -> None: ...


def _code(error: ResourceNotFoundError) -> object:
    # The storage SDK attaches `error_code` to the errors it raises; it is not declared on them.
    return getattr(error, "error_code", None)


class AzureBlob:
    """A `Blob` in Azure Storage. `etag=None` writes only if the blob does not exist yet."""

    def __init__(self, client: BlobClient) -> None:
        self._client = client

    async def read(self) -> tuple[bytes, str] | None:
        try:
            download = await self._client.download_blob()
            return await download.readall(), str(download.properties.etag)
        except ResourceNotFoundError as error:
            # Only a missing blob means "no starts yet"; a missing container or account is a fault.
            if _code(error) == StorageErrorCode.blob_not_found:
                return None
            raise LedgerError("the start ledger is unavailable") from error
        except AzureError as error:
            raise LedgerError("the start ledger is unavailable") from error

    async def write(self, data: bytes, *, etag: str | None) -> None:
        try:
            if etag is None:
                await self._client.upload_blob(data, overwrite=False)
            else:
                await self._client.upload_blob(
                    data, overwrite=True, etag=etag, match_condition=MatchConditions.IfNotModified
                )
        except (ResourceExistsError, ResourceModifiedError):
            raise LedgerConflictError from None
        except ResourceNotFoundError as error:
            # Deleted since it was read: If-Match on a missing blob is a 404, not a 412.
            if etag is not None and _code(error) == StorageErrorCode.blob_not_found:
                raise LedgerConflictError from None
            raise LedgerError("the start ledger is unavailable") from error
        except AzureError as error:
            raise LedgerError("the start ledger is unavailable") from error


def _starts(content: bytes) -> tuple[float, ...]:
    try:
        starts = json.loads(content)["starts"]
    except (ValueError, TypeError, KeyError):
        raise LedgerError("the start ledger is unreadable") from None
    if not isinstance(starts, list) or not all(
        isinstance(t, int | float) and not isinstance(t, bool) for t in starts
    ):
        raise LedgerError("the start ledger is unreadable")
    return tuple(float(t) for t in starts)


class BlobStartLedger:
    """A `StartLedger` in one blob."""

    def __init__(self, blob: Blob) -> None:
        self._blob = blob

    async def _read(self) -> tuple[tuple[float, ...], str | None]:
        found = await self._blob.read()
        return ((), None) if found is None else (_starts(found[0]), found[1])

    async def recent(self, since: float) -> tuple[float, ...]:
        starts, _ = await self._read()
        return tuple(t for t in starts if t >= since)

    async def claim(self, started: float, check: Callable[[tuple[float, ...]], None]) -> None:
        starts, etag = await self._read()
        check(starts)
        data = json.dumps({"starts": [*starts, started][-KEPT_STARTS:]}).encode()
        try:
            # Written over the version just checked: if another start landed since, this loses.
            await self._blob.write(data, etag=etag)
        except LedgerConflictError:
            raise MatchdayBusyError("another start was recorded at the same moment") from None


@asynccontextmanager
async def blob_start_ledger(url: str, client_id: str) -> AsyncIterator[BlobStartLedger]:
    """The ledger at `url`, reached with the app's managed identity (or the developer's own
    credential when `client_id` is empty). The credential and client close on exit."""
    async with (
        DefaultAzureCredential(managed_identity_client_id=client_id or None) as credential,
        BlobClient.from_blob_url(url, credential=credential) as client,
    ):
        yield BlobStartLedger(AzureBlob(client))
