"""The policy book kept in Blob Storage: one blob per partner, `<tenant>.json`, holding its whole
history. The container keeps blob versions and soft-deletes, so an overwrite is recoverable."""

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import get_args

from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import ContainerClient
from pydantic import ValidationError

from fourth_official_contracts import PolicyHistory, TenantId, parse_policy_history

# A history of 500 versions is well under this.
MAX_HISTORY_BYTES = 4 * 1024 * 1024


class UnreadableBookError(RuntimeError):
    """A kept history that no longer reads: the API stops rather than silently replacing it."""


class BlobBookStore:
    def __init__(self, container: ContainerClient) -> None:
        self._container = container

    async def load(self) -> Mapping[TenantId, PolicyHistory]:
        histories: dict[TenantId, PolicyHistory] = {}
        for tenant_id in get_args(TenantId):
            try:
                download = await self._container.download_blob(f"{tenant_id}.json")
            except ResourceNotFoundError:
                continue
            data = await download.readall()
            try:
                if len(data) > MAX_HISTORY_BYTES:
                    raise ValueError("too large")
                histories[tenant_id] = parse_policy_history(json.loads(data))
            except (ValueError, ValidationError) as error:
                raise UnreadableBookError(
                    f"the kept policy history of {tenant_id} no longer reads"
                ) from error
        return histories

    async def save(self, history: PolicyHistory) -> None:
        data = json.dumps(history.to_wire(), ensure_ascii=False).encode("utf-8")
        await self._container.upload_blob(f"{history.tenant_id}.json", data, overwrite=True)


@asynccontextmanager
async def azure_policy_book(container_url: str, client_id: str) -> AsyncIterator[BlobBookStore]:
    """The Blob store, as the managed identity `client_id` (or the developer's credential when it
    is empty). Every client closes on exit."""
    async with (
        DefaultAzureCredential(managed_identity_client_id=client_id or None) as credential,
        ContainerClient.from_container_url(container_url, credential=credential) as container,
    ):
        yield BlobBookStore(container)
