"""Provenance in Azure: the studio's Key Vault key signs (ES256, keyless through a managed
identity; the private key never leaves the vault), and Blob Storage keeps one record per item
(versioning keeps every earlier issue)."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.keys.crypto import SignatureAlgorithm
from azure.keyvault.keys.crypto.aio import CryptographyClient
from azure.storage.blob.aio import ContainerClient
from pydantic import ValidationError

from fourth_official_contracts import SignedProvenance, parse_signed_provenance
from fourth_official_provenance.store import UnreadableRecordError

PREFIX = "records/"


class KeyVaultSigner:
    algorithm: Literal["ES256"] = "ES256"

    def __init__(self, client: CryptographyClient, key_id: str) -> None:
        self._client = client
        self.key_id = key_id

    async def sign(self, digest: bytes) -> bytes:
        result = await self._client.sign(SignatureAlgorithm.es256, digest)
        return bytes(result.signature)

    async def verify(self, digest: bytes, signature: bytes) -> bool:
        result = await self._client.verify(SignatureAlgorithm.es256, digest, signature)
        return bool(result.is_valid)


class BlobProvenanceStore:
    def __init__(self, container: ContainerClient) -> None:
        self._container = container

    async def put(self, signed: SignedProvenance) -> None:
        data = json.dumps(signed.to_wire(), ensure_ascii=False).encode("utf-8")
        await self._container.upload_blob(
            f"{PREFIX}{signed.record.item_id}.json", data, overwrite=True
        )

    async def get(self, item_id: str) -> SignedProvenance | None:
        try:
            download = await self._container.download_blob(f"{PREFIX}{item_id}.json")
        except ResourceNotFoundError:
            return None
        raw = await download.readall()
        try:
            return parse_signed_provenance(json.loads(raw))
        except (ValueError, ValidationError):
            raise UnreadableRecordError("the stored record no longer reads") from None


@asynccontextmanager
async def azure_provenance(
    key_id: str, container_url: str, client_id: str
) -> AsyncIterator[tuple[KeyVaultSigner, BlobProvenanceStore]]:
    """The Key Vault signer and the Blob store, as the managed identity `client_id` (or the
    developer's credential when it is empty). Every client closes on exit."""
    async with (
        DefaultAzureCredential(managed_identity_client_id=client_id or None) as credential,
        CryptographyClient(key_id, credential) as crypto,
        ContainerClient.from_container_url(container_url, credential=credential) as container,
    ):
        yield KeyVaultSigner(crypto, key_id), BlobProvenanceStore(container)
