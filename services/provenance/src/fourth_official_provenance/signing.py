"""Signing a record and checking a signed one.

The hash of a record's canonical bytes is signed: with the studio's Key Vault key in Azure (ES256,
keyless through the API's managed identity; the private key never leaves the vault), or with a
local HMAC key in development and tests (HS256). Checking recomputes the hash from the record as
stored, so any change to the record after signing is detected.
"""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Literal, Protocol

from fourth_official_contracts import ProvenanceRecord, SignedProvenance, canonical_bytes


class Signer(Protocol):
    @property
    def algorithm(self) -> Literal["ES256", "HS256"]: ...

    @property
    def key_id(self) -> str: ...

    async def sign(self, digest: bytes) -> bytes: ...

    async def verify(self, digest: bytes, signature: bytes) -> bool: ...


class LocalSigner:
    """HMAC-SHA256 with a key held in the process: for development and tests only."""

    algorithm: Literal["HS256"] = "HS256"

    def __init__(self, key: bytes | None = None, *, key_id: str = "local:development") -> None:
        key = secrets.token_bytes(32) if key is None else key
        if len(key) < 32:
            raise ValueError("a local signing key needs at least 32 bytes")
        self._key = key
        self.key_id = key_id

    async def sign(self, digest: bytes) -> bytes:
        return hmac.new(self._key, digest, hashlib.sha256).digest()

    async def verify(self, digest: bytes, signature: bytes) -> bool:
        return hmac.compare_digest(await self.sign(digest), signature)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


async def sign_record(record: ProvenanceRecord, signer: Signer) -> SignedProvenance:
    digest = hashlib.sha256(canonical_bytes(record)).digest()
    return SignedProvenance(
        record=record,
        content_hash=digest.hex(),
        signature=_b64(await signer.sign(digest)),
        algorithm=signer.algorithm,
        key_id=signer.key_id,
    )


@dataclass(frozen=True, slots=True)
class Verification:
    valid: bool
    # Why it does not verify, in words safe to show; None when it does.
    reason: str | None = None


async def verify_signed(signed: SignedProvenance, signer: Signer) -> Verification:
    """Whether the stored record is the one that was signed, and signed with this key."""
    if signed.key_id != signer.key_id or signed.algorithm != signer.algorithm:
        return Verification(False, "signed with another key")
    digest = hashlib.sha256(canonical_bytes(signed.record)).digest()
    if digest.hex() != signed.content_hash:
        return Verification(False, "the record has changed since it was signed")
    try:
        signature = _unb64(signed.signature)
    except ValueError:
        return Verification(False, "the signature does not match")
    if not await signer.verify(digest, signature):
        return Verification(False, "the signature does not match")
    return Verification(True)
