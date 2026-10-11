"""Where signed records are kept: one per partner item, the latest issue."""

from typing import Protocol

from fourth_official_contracts import SignedProvenance


class ProvenanceStore(Protocol):
    async def put(self, signed: SignedProvenance) -> None: ...

    async def get(self, item_id: str) -> SignedProvenance | None: ...


class InMemoryStore:
    """Records held in the process: for development and tests."""

    def __init__(self) -> None:
        self._records: dict[str, SignedProvenance] = {}

    async def put(self, signed: SignedProvenance) -> None:
        self._records[signed.record.item_id] = signed

    async def get(self, item_id: str) -> SignedProvenance | None:
        return self._records.get(item_id)
