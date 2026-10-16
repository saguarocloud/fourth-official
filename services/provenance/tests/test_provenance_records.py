"""Every partner item's provenance: built from the feed, signed, stored, and checked. A record that
changes after it was signed no longer verifies."""

import hashlib
from datetime import UTC, datetime

import anyio
import pytest

from fourth_official_contracts import InsightEntry, TenantItemEntry, canonical_bytes
from fourth_official_provenance import (
    InMemoryStore,
    LocalSigner,
    record_for,
    sign_record,
    verify_signed,
)
from provenance_fixtures import FEED

NOW = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)


def items() -> list[TenantItemEntry]:
    return [e for e in FEED if isinstance(e, TenantItemEntry)]


def canonical_of(item: TenantItemEntry) -> InsightEntry | None:
    insight_id = item.localized.insight_id if item.localized else None
    return next(
        (e for e in FEED if isinstance(e, InsightEntry) and e.insight.insight_id == insight_id),
        None,
    )


def first_narrative(tenant: str) -> TenantItemEntry:
    return next(i for i in items() if i.tenant_id == tenant and i.localized is not None)


def test_a_record_names_the_item_its_words_their_evidence_and_who_wrote_them() -> None:
    item = first_narrative("tribuna-austral")

    record = record_for(item, canonical_of(item), issued_at=NOW, corrections=())

    assert record is not None
    assert (record.item_id, record.tenant_id, record.version) == (
        item.overlay.item_id,
        "tribuna-austral",
        1,
    )
    assert record.headline == item.rendered.headline  # type: ignore[union-attr]
    assert [c.text for c in record.claims] == list(item.rendered.claims)  # type: ignore[union-attr]
    assert record.claims[0].evidence == item.localized.claims[0].evidence  # type: ignore[union-attr]
    assert record.canonical is not None
    assert record.localized == item.localized.provenance  # type: ignore[union-attr]
    assert record.feed_entry == item.entry_seq
    assert record.issuer == "Meridian League Studios"


def test_a_graphic_no_agent_wrote_has_no_record() -> None:
    bug = next(i for i in items() if i.item_kind == "score")

    assert record_for(bug, None, issued_at=NOW, corrections=()) is None


def test_a_signed_record_verifies_and_a_changed_one_does_not() -> None:
    item = first_narrative("northlight-sport")
    record = record_for(item, canonical_of(item), issued_at=NOW, corrections=())
    assert record is not None
    signer = LocalSigner(b"k" * 32)

    async def run() -> None:
        signed = await sign_record(record, signer)
        assert signed.algorithm == "HS256"
        assert (await verify_signed(signed, signer)).valid

        tampered = signed.model_copy(
            update={"record": record.model_copy(update={"headline": "Something else"})}
        )
        verdict = await verify_signed(tampered, signer)
        assert not verdict.valid
        assert verdict.reason == "the record has changed since it was signed"

        forged = signed.model_copy(update={"signature": "Zm9yZ2VkLXNpZ25hdHVyZQ"})
        assert (await verify_signed(forged, signer)).reason == "the signature does not match"

        other = LocalSigner(b"o" * 32, key_id="local:other")
        assert (await verify_signed(signed, other)).reason == "signed with another key"

    anyio.run(run)


def test_the_hash_is_of_the_canonical_bytes() -> None:
    item = first_narrative("rheinblick-sport")
    record = record_for(item, canonical_of(item), issued_at=NOW, corrections=("c-m42-01",))
    assert record is not None

    async def run() -> None:
        signed = await sign_record(record, LocalSigner(b"k" * 32))
        assert signed.content_hash == hashlib.sha256(canonical_bytes(record)).hexdigest()
        assert signed.record.corrections == ("c-m42-01",)

    anyio.run(run)


def test_the_store_keeps_the_latest_record_per_item() -> None:
    item = first_narrative("northlight-sport")
    store = InMemoryStore()
    signer = LocalSigner(b"k" * 32)

    async def run() -> None:
        first = record_for(item, canonical_of(item), issued_at=NOW, corrections=())
        later = record_for(item, canonical_of(item), issued_at=NOW, corrections=("c-m42-01",))
        assert first is not None
        assert later is not None
        await store.put(await sign_record(first, signer))
        await store.put(await sign_record(later, signer))
        kept = await store.get(item.overlay.item_id)
        assert kept is not None
        assert kept.record.corrections == ("c-m42-01",)
        assert await store.get("it-northlight-sport-in-nothing-v1") is None

    anyio.run(run)


def test_a_local_key_must_be_long_enough() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        LocalSigner(b"short")


def test_a_record_signs_every_attempt_but_never_what_it_cost() -> None:
    item = first_narrative("tribuna-austral")
    metered = item.model_copy(
        update={
            "attempts": tuple(
                a.model_copy(update={"input_tokens": 900, "output_tokens": 80})
                for a in item.attempts
            )
        }
    )

    record = record_for(metered, canonical_of(item), issued_at=NOW, corrections=())
    unmetered = record_for(item, canonical_of(item), issued_at=NOW, corrections=())

    assert record is not None
    assert unmetered is not None
    assert [a.outcome for a in record.attempts] == [a.outcome for a in item.attempts]
    assert canonical_bytes(record) == canonical_bytes(unmetered)
    assert b"Tokens" not in canonical_bytes(record)
