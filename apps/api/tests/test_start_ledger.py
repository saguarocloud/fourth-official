"""The durable start ledger: matchday starts kept in one blob, recorded only if nobody else
recorded one since the guards read it."""

import json

import anyio
import pytest
from azure.core import MatchConditions
from azure.core.exceptions import (
    HttpResponseError,
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)
from azure.storage.blob import StorageErrorCode

from fourth_official_api.start_ledger import (
    KEPT_STARTS,
    AzureBlob,
    BlobStartLedger,
    LedgerConflictError,
    LedgerError,
)
from fourth_official_match_data import demo_store
from fourth_official_replay import Matchday
from fourth_official_replay.matchday import MatchdayBusyError


class MemoryBlob:
    """A blob with the service's preconditions: writes name the version they replace."""

    def __init__(self, content: bytes | None = None) -> None:
        self.content = content
        self.version = 0 if content is None else 1
        self.writes = 0

    async def read(self) -> tuple[bytes, str] | None:
        if self.content is None:
            return None
        return self.content, str(self.version)

    async def write(self, data: bytes, *, etag: str | None) -> None:
        current = None if self.content is None else str(self.version)
        if etag != current:
            raise LedgerConflictError
        self.content, self.version = data, self.version + 1
        self.writes += 1


def starts_in(blob: MemoryBlob) -> list[float]:
    assert blob.content is not None
    return list(json.loads(blob.content)["starts"])


def accept(starts: tuple[float, ...]) -> None:
    return None


def test_an_empty_ledger_has_no_starts_and_records_the_first() -> None:
    blob = MemoryBlob()
    ledger = BlobStartLedger(blob)
    checked: list[tuple[float, ...]] = []

    async def run() -> tuple[float, ...]:
        seen = await ledger.recent(0.0)
        await ledger.claim(10.0, checked.append)
        return seen

    assert anyio.run(run) == ()
    assert checked == [()]
    assert starts_in(blob) == [10.0]


def test_recent_starts_are_those_since_the_time_asked() -> None:
    blob = MemoryBlob(json.dumps({"starts": [1.0, 5.0, 9.0]}).encode())

    assert anyio.run(BlobStartLedger(blob).recent, 5.0) == (5.0, 9.0)


class RacedBlob(MemoryBlob):
    """Another process writes a start right after each read."""

    async def read(self) -> tuple[bytes, str] | None:
        found = await super().read()
        self.content = json.dumps({"starts": [1.0, 2.0]}).encode()
        self.version += 1
        return found


def test_a_start_recorded_elsewhere_between_check_and_write_loses_the_race() -> None:
    blob = RacedBlob(json.dumps({"starts": [1.0]}).encode())

    with pytest.raises(MatchdayBusyError, match="another start"):
        anyio.run(BlobStartLedger(blob).claim, 3.0, accept)
    assert starts_in(blob) == [1.0, 2.0]
    assert blob.writes == 0


def test_a_refused_check_records_nothing() -> None:
    blob = MemoryBlob(json.dumps({"starts": [1.0]}).encode())

    def refuse(starts: tuple[float, ...]) -> None:
        raise MatchdayBusyError("not yet")

    with pytest.raises(MatchdayBusyError, match="not yet"):
        anyio.run(BlobStartLedger(blob).claim, 2.0, refuse)
    assert blob.writes == 0


def test_only_the_latest_starts_are_kept() -> None:
    blob = MemoryBlob(json.dumps({"starts": [float(n) for n in range(KEPT_STARTS)]}).encode())

    anyio.run(BlobStartLedger(blob).claim, 1000.0, accept)

    assert len(starts_in(blob)) == KEPT_STARTS
    assert starts_in(blob)[-1] == 1000.0


@pytest.mark.parametrize(
    "content",
    [b"not json", b"[]", b'{"starts": "x"}', b'{"starts": [1, "x"]}', b'{"starts": [true]}'],
)
def test_a_ledger_it_cannot_read_stops_every_start(content: bytes) -> None:
    ledger = BlobStartLedger(MemoryBlob(content))

    with pytest.raises(LedgerError, match="unreadable"):
        anyio.run(ledger.recent, 0.0)


def test_the_matchday_guards_read_and_write_through_it() -> None:
    blob = MemoryBlob()

    async def explain_nothing(*_: object) -> object:
        raise AssertionError("not reached")

    async def run() -> None:
        day = Matchday(demo_store(), explain_nothing, ledger=BlobStartLedger(blob))  # type: ignore[arg-type]
        await day.start(now=100.0)
        await day.stop()
        with pytest.raises(MatchdayBusyError, match="again in"):
            await day.start(now=200.0)

    anyio.run(run)
    assert starts_in(blob) == [100.0]


class FakeDownload:
    def __init__(self, data: bytes, etag: str) -> None:
        self.data, self.properties = data, type("P", (), {"etag": etag})()

    async def readall(self) -> bytes:
        return self.data


def not_found(code: object) -> ResourceNotFoundError:
    error = ResourceNotFoundError("not found")
    setattr(error, "error_code", code)  # noqa: B010 - the SDK attaches it the same way
    return error


class FakeBlobClient:
    """The slice of `azure.storage.blob.aio.BlobClient` the adapter uses."""

    def __init__(
        self, *, missing: Exception | None = None, conflict: Exception | None = None
    ) -> None:
        self.missing, self.conflict = missing, conflict
        self.uploads: list[dict[str, object]] = []

    async def download_blob(self) -> FakeDownload:
        if self.missing is not None:
            raise self.missing
        return FakeDownload(b'{"starts": []}', '"0x1"')

    async def upload_blob(self, data: bytes, **kwargs: object) -> None:
        if self.conflict is not None:
            raise self.conflict
        self.uploads.append({"data": data, **kwargs})


def test_the_azure_adapter_reads_with_the_etag_and_writes_on_condition() -> None:
    client = FakeBlobClient()
    blob = AzureBlob(client)  # type: ignore[arg-type]

    async def run() -> tuple[bytes, str] | None:
        read = await blob.read()
        await blob.write(b"x", etag='"0x1"')
        await blob.write(b"y", etag=None)
        return read

    assert anyio.run(run) == (b'{"starts": []}', '"0x1"')
    first, second = client.uploads
    assert first["etag"] == '"0x1"'
    assert first["overwrite"] is True
    assert first["match_condition"] is MatchConditions.IfNotModified
    assert second["overwrite"] is False


def test_the_azure_adapter_reads_a_missing_blob_as_no_starts() -> None:
    client = FakeBlobClient(missing=not_found(StorageErrorCode.blob_not_found))

    assert anyio.run(AzureBlob(client).read) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "error",
    [
        not_found(StorageErrorCode.container_not_found),
        not_found(StorageErrorCode.resource_not_found),
        HttpResponseError("forbidden"),
    ],
)
def test_the_azure_adapter_never_reads_a_missing_container_or_a_failure_as_empty(
    error: Exception,
) -> None:
    with pytest.raises(LedgerError, match="unavailable"):
        anyio.run(AzureBlob(FakeBlobClient(missing=error)).read)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("error", "etag"),
    [
        (ResourceModifiedError("precondition"), '"0x1"'),
        (ResourceExistsError("exists"), None),
        # Deleted between the read and the write: If-Match on a missing blob is a 404.
        (not_found(StorageErrorCode.blob_not_found), '"0x1"'),
    ],
)
def test_the_azure_adapter_reports_lost_races(error: Exception, etag: str | None) -> None:
    blob = AzureBlob(FakeBlobClient(conflict=error))  # type: ignore[arg-type]

    async def write() -> None:
        await blob.write(b"x", etag=etag)

    with pytest.raises(LedgerConflictError):
        anyio.run(write)


def test_the_azure_adapter_reports_other_write_failures_as_unavailable() -> None:
    blob = AzureBlob(FakeBlobClient(conflict=HttpResponseError("forbidden")))  # type: ignore[arg-type]

    async def write() -> None:
        await blob.write(b"x", etag='"0x1"')

    with pytest.raises(LedgerError, match="unavailable"):
        anyio.run(write)


def test_two_first_starts_on_an_empty_ledger_cannot_both_be_recorded() -> None:
    blob = MemoryBlob()
    first, second = BlobStartLedger(blob), BlobStartLedger(blob)

    async def run() -> None:
        async def claim_after_the_other_reads() -> None:
            await first.claim(1.0, accept)

        def both_read_empty(starts: tuple[float, ...]) -> None:
            assert starts == ()

        # The second claims while the first is between its read and its write.
        original = blob.read

        async def read_then_let_the_other_win() -> tuple[bytes, str] | None:
            found = await original()
            blob.read = original  # type: ignore[method-assign]
            await claim_after_the_other_reads()
            return found

        blob.read = read_then_let_the_other_win  # type: ignore[method-assign]
        await second.claim(2.0, both_read_empty)

    with pytest.raises(MatchdayBusyError, match="another start"):
        anyio.run(run)
    assert starts_in(blob) == [1.0]


def test_a_refused_first_start_writes_nothing() -> None:
    blob = MemoryBlob()

    def refuse(starts: tuple[float, ...]) -> None:
        raise MatchdayBusyError("not yet")

    with pytest.raises(MatchdayBusyError):
        anyio.run(BlobStartLedger(blob).claim, 1.0, refuse)
    assert blob.content is None
