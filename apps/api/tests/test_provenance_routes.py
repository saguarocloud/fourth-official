"""Every partner item's provenance, issued as the match is published and checked when read: a
record changed after it was signed says so."""

from collections.abc import Iterator

import anyio
import pytest
from fastapi.testclient import TestClient

from fourth_official_api.main import create_app
from fourth_official_api.provenance import Issuer
from fourth_official_api.settings import Settings
from fourth_official_contracts import TenantItemEntry
from fourth_official_match_data import demo_store
from fourth_official_provenance import InMemoryStore, LocalSigner
from fourth_official_replay import Matchday, ReplayConfig
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
