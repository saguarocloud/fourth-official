"""The policy book kept in Blob Storage: one blob per partner, read back through the contract."""

import json
from datetime import UTC, datetime

import anyio
import pytest
from azure.core.exceptions import ResourceNotFoundError

from fourth_official_api.policy_store import BlobBookStore, UnreadableBookError
from fourth_official_policy import bundled_store
from fourth_official_policy.book import PolicyBook


class FakeDownload:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def readall(self) -> bytes:
        return self._data


class FakeContainer:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def upload_blob(self, name: str, data: bytes, **kwargs: object) -> None:
        assert kwargs.get("overwrite") is True
        self.blobs[name] = data

    async def download_blob(self, name: str) -> FakeDownload:
        if name not in self.blobs:
            raise ResourceNotFoundError("no blob")
        return FakeDownload(self.blobs[name])


def opened(container: FakeContainer) -> PolicyBook:
    book = PolicyBook(
        [loaded.policy for loaded in bundled_store().all()],
        BlobBookStore(container),  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 10, 12, 9, 0, tzinfo=UTC),
    )
    anyio.run(book.open)
    return book


def test_a_new_book_is_written_one_blob_per_partner() -> None:
    container = FakeContainer()
    opened(container)

    assert sorted(container.blobs) == [
        "northlight-sport.json",
        "rheinblick-sport.json",
        "tribuna-austral.json",
    ]


def test_an_edit_is_read_back_after_a_restart() -> None:
    container = FakeContainer()
    first = opened(container)
    policy = first.current("rheinblick-sport").to_wire() | {"maxItemsPerMinute": 2}
    anyio.run(lambda: first.edit("rheinblick-sport", policy, base_version=1, reason="Quieter"))

    again = opened(container)

    assert again.current("rheinblick-sport").max_items_per_minute == 2
    assert again.history("rheinblick-sport").changes[-1].reason == "Quieter"


def test_a_kept_history_that_no_longer_reads_stops_the_start_rather_than_being_replaced() -> None:
    container = FakeContainer()
    opened(container)
    container.blobs["rheinblick-sport.json"] = json.dumps({"tenantId": "x"}).encode()

    with pytest.raises(UnreadableBookError, match="rheinblick-sport"):
        opened(container)
