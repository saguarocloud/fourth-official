"""Every partner item's provenance, issued as the match is published and checked when read: a
record changed after it was signed says so."""

from collections.abc import Iterator

import anyio
import pytest
from fastapi.testclient import TestClient

from fourth_official_api.main import create_app
from fourth_official_api.provenance import READS_PER_MINUTE, Issuer
from fourth_official_api.settings import Settings
from fourth_official_contracts import TenantItemEntry
from fourth_official_match_data import demo_store
from fourth_official_provenance import InMemoryStore, LocalSigner
from fourth_official_replay import Matchday, ReplayConfig
from provenance_fixtures import FEED as FEED_M42
from test_partners import no_wait, partners, template_only

STUDIO = {"X-Requested-By": "fourth-official"}


@pytest.fixture
def played() -> Iterator[tuple[TestClient, Matchday, InMemoryStore]]:
    day = Matchday(
        demo_store(), template_only, config=ReplayConfig(), sleep=no_wait, partners=partners
    )
    store = InMemoryStore()
    issuer = Issuer(LocalSigner(b"k" * 32), store)
    app = create_app(Settings(version="test"), matchday=day, provenance=issuer)
    with TestClient(app) as client:
        assert client.post("/api/matchday", headers=STUDIO).status_code == 202
        assert client.portal is not None
        client.portal.call(day.wait)
        client.portal.call(issued, issuer, day)
        yield client, day, store


async def issued(issuer: Issuer, day: Matchday) -> None:
    """Wait until the issuer has caught up with every feed."""
    with anyio.fail_after(60):
        while not all(issuer.caught_up(day.feed(m)) for m in ("m42", "m43", "m44")):
            await anyio.sleep(0.01)


def narrative(day: Matchday, tenant: str) -> TenantItemEntry:
    return next(
        e
        for e in day.feed("m42").entries
        if isinstance(e, TenantItemEntry) and e.tenant_id == tenant and e.localized is not None
    )


def test_a_published_item_has_a_signed_record_that_verifies(
    played: tuple[TestClient, Matchday, InMemoryStore],
) -> None:
    client, day, _ = played
    item = narrative(day, "tribuna-austral")

    answer = client.get(f"/api/items/{item.overlay.item_id}/provenance")

    assert answer.status_code == 200
    assert answer.headers["cache-control"] == "no-store"
    body = answer.json()
    assert body["verification"] == {"valid": True, "reason": None}
    record = body["provenance"]["record"]
    assert record["itemId"] == item.overlay.item_id
    assert record["issuer"] == "Meridian League Studios"
    assert body["provenance"]["algorithm"] == "HS256"


def test_a_record_lists_the_corrections_that_reached_its_item(
    played: tuple[TestClient, Matchday, InMemoryStore],
) -> None:
    client, day, _ = played
    pulled = next(
        e
        for e in day.feed("m42").entries
        if isinstance(e, TenantItemEntry) and e.state == "retracted"
    )

    record = client.get(f"/api/items/{pulled.overlay.item_id}/provenance").json()["provenance"]

    assert record["record"]["state"] == "retracted"
    assert record["record"]["corrections"]


def test_a_record_changed_after_signing_says_so(
    played: tuple[TestClient, Matchday, InMemoryStore],
) -> None:
    client, day, store = played
    item = narrative(day, "northlight-sport")
    assert client.portal is not None
    signed = client.portal.call(store.get, item.overlay.item_id)
    assert signed is not None
    tampered = signed.model_copy(
        update={"record": signed.record.model_copy(update={"headline": "Something else"})}
    )
    client.portal.call(store.put, tampered)

    body = client.get(f"/api/items/{item.overlay.item_id}/provenance").json()

    assert body["verification"] == {
        "valid": False,
        "reason": "the record has changed since it was signed",
    }


def test_a_graphic_no_agent_wrote_and_an_unknown_item_have_no_record(
    played: tuple[TestClient, Matchday, InMemoryStore],
) -> None:
    client, day, _ = played
    bug = next(
        e
        for e in day.feed("m42").entries
        if isinstance(e, TenantItemEntry) and e.item_kind == "score"
    )

    assert client.get(f"/api/items/{bug.overlay.item_id}/provenance").status_code == 404
    assert client.get("/api/items/it-northlight-sport-in-m42-x-v1/provenance").status_code == 404
    assert client.get("/api/items/<script>/provenance").status_code == 422


# --- Trust: what a blob writer without the key can and cannot do ------------------------------


def test_a_genuine_record_stored_under_another_item_does_not_verify(
    played: tuple[TestClient, Matchday, InMemoryStore],
) -> None:
    client, day, store = played
    a, b = narrative(day, "northlight-sport"), narrative(day, "rheinblick-sport")
    assert client.portal is not None
    genuine = client.portal.call(store.get, a.overlay.item_id)
    assert genuine is not None
    store._records[b.overlay.item_id] = genuine

    body = client.get(f"/api/items/{b.overlay.item_id}/provenance").json()

    assert body["verification"] == {
        "valid": False,
        "reason": "the record stored here is of another item",
    }


def test_an_earlier_genuine_issue_restored_over_a_later_one_does_not_verify(
    played: tuple[TestClient, Matchday, InMemoryStore],
) -> None:
    client, day, store = played
    pulled = next(
        e
        for e in day.feed("m42").entries
        if isinstance(e, TenantItemEntry) and e.state == "retracted"
    )
    earlier = next(
        e
        for e in day.feed("m42").entries
        if isinstance(e, TenantItemEntry) and e.overlay.item_id == pulled.overlay.item_id
    )
    assert client.portal is not None
    issuer: Issuer = client.app.state.provenance  # type: ignore[attr-defined]
    old = client.portal.call(issuer.issue, earlier, day.feed("m42").entries, False)
    assert old is not None
    client.portal.call(store.put, old)

    body = client.get(f"/api/items/{pulled.overlay.item_id}/provenance").json()

    assert body["verification"] == {
        "valid": False,
        "reason": "a later issue of this record exists; this one is out of date",
    }


def test_reading_is_rate_limited(played: tuple[TestClient, Matchday, InMemoryStore]) -> None:
    client, day, _ = played
    item = narrative(day, "northlight-sport")
    where = f"/api/items/{item.overlay.item_id}/provenance"
    headers = {"X-Forwarded-For": "203.0.113.7"}

    answers = [client.get(where, headers=headers).status_code for _ in range(READS_PER_MINUTE + 1)]

    assert answers[:-1] == [200] * READS_PER_MINUTE
    assert answers[-1] == 429


# --- Robustness ----------------------------------------------------------------------------------


class Flaky:
    """A signer that fails its first `failures` calls, then signs."""

    algorithm = "HS256"

    def __init__(self, failures: int) -> None:
        self._inner = LocalSigner(b"k" * 32)
        self.key_id = self._inner.key_id
        self.failures = failures

    async def sign(self, digest: bytes) -> bytes:
        if self.failures > 0:
            self.failures -= 1
            raise RuntimeError("vault busy")
        return await self._inner.sign(digest)

    async def verify(self, digest: bytes, signature: bytes) -> bool:
        return await self._inner.verify(digest, signature)


def test_a_record_that_fails_to_sign_is_retried_until_it_is_issued() -> None:
    store = InMemoryStore()
    issuer = Issuer(Flaky(failures=2), store, backoff=(0.0, 0.0, 0.0))  # type: ignore[arg-type]
    item = next(e for e in FEED_M42 if isinstance(e, TenantItemEntry) and e.localized is not None)

    signed = anyio.run(issuer.issue, item, FEED_M42, True)

    assert signed is not None
    assert anyio.run(store.get, item.overlay.item_id) == signed


def test_a_record_that_never_signs_leaves_the_feed_not_caught_up() -> None:
    store = InMemoryStore()
    issuer = Issuer(Flaky(failures=99), store, backoff=(0.0,))  # type: ignore[arg-type]
    item = next(e for e in FEED_M42 if isinstance(e, TenantItemEntry) and e.localized is not None)

    assert anyio.run(issuer.issue, item, FEED_M42, True) is None
    assert issuer.failing == {item.overlay.item_id}
