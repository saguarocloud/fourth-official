"""The Azure side: signing with the studio's Key Vault key, and keeping records in Blob Storage.
Both are exercised against fakes of the Azure clients; the wiring is checked in Azure itself."""

from datetime import UTC, datetime
from types import SimpleNamespace

import anyio
import pytest
from azure.core.exceptions import ResourceNotFoundError
from azure.keyvault.keys.crypto import SignatureAlgorithm

from fourth_official_contracts import ProvenanceRecord, TenantItemEntry
from fourth_official_provenance import record_for, sign_record, verify_signed
from fourth_official_provenance.azure import (
    BlobProvenanceStore,
    KeyVaultSigner,
    UnreadableRecordError,
)
from provenance_fixtures import FEED

KEY_ID = "https://kv-x.vault.azure.net/keys/provenance/0123456789abcdef0123456789abcdef"
NOW = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)


class FakeCrypto:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def sign(self, algorithm: SignatureAlgorithm, digest: bytes) -> SimpleNamespace:
        self.calls.append(("sign", algorithm))
        return SimpleNamespace(signature=b"sig:" + digest)

    async def verify(
        self, algorithm: SignatureAlgorithm, digest: bytes, signature: bytes
    ) -> SimpleNamespace:
        self.calls.append(("verify", algorithm))
        return SimpleNamespace(is_valid=signature == b"sig:" + digest)


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


def a_record() -> ProvenanceRecord:
    item = next(e for e in FEED if isinstance(e, TenantItemEntry) and e.localized is not None)
    record = record_for(item, None, issued_at=NOW, corrections=())
    assert record is not None
    return record


def test_key_vault_signs_the_digest_with_es256_and_checks_it() -> None:
    crypto = FakeCrypto()
    signer = KeyVaultSigner(crypto, KEY_ID)  # type: ignore[arg-type]

    async def run() -> None:
        signed = await sign_record(a_record(), signer)
        assert (signed.algorithm, signed.key_id) == ("ES256", KEY_ID)
        assert (await verify_signed(signed, signer)).valid

    anyio.run(run)
    assert crypto.calls == [
        ("sign", SignatureAlgorithm.es256),
        ("verify", SignatureAlgorithm.es256),
    ]


def test_records_are_kept_one_blob_per_item_and_read_back() -> None:
    container = FakeContainer()
    store = BlobProvenanceStore(container)  # type: ignore[arg-type]
    signer = KeyVaultSigner(FakeCrypto(), KEY_ID)  # type: ignore[arg-type]

    async def run() -> None:
        signed = await sign_record(a_record(), signer)
        await store.put(signed)
        assert list(container.blobs) == [f"records/{signed.record.item_id}.json"]
        assert await store.get(signed.record.item_id) == signed
        assert await store.get("it-northlight-sport-in-m42-nothing-v1") is None

    anyio.run(run)


def test_a_stored_record_that_no_longer_reads_is_reported_not_trusted() -> None:
    container = FakeContainer()
    container.blobs["records/it-x-v1.json"] = b'{"record": "tampered"}'
    store = BlobProvenanceStore(container)  # type: ignore[arg-type]

    with pytest.raises(UnreadableRecordError):
        anyio.run(store.get, "it-x-v1")
