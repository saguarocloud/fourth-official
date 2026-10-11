"""An editor decides on a held item: approve puts it on air, reject keeps it off with the reason.
Decisions come only from the studio's own pages, like starting the matchday."""

from collections.abc import Iterator

import anyio
import pytest
from fastapi.testclient import TestClient

from fourth_official_api.main import create_app
from fourth_official_api.settings import Settings
from fourth_official_contracts import TenantItemEntry, parse_feed_entry
from fourth_official_match_data import demo_store
from fourth_official_replay import Matchday, ReplayConfig
from test_partners import no_wait, partners, template_only

STUDIO = {"X-Requested-By": "fourth-official"}


class Paused:
    """A matchday whose featured match, once played, waits before full time until released: its
    held items are on the feed and the feed is still open."""

    def __init__(self) -> None:
        self.released = anyio.Event()
        self.day = Matchday(
            demo_store(), template_only, config=ReplayConfig(), sleep=no_wait, partners=partners
        )
        feed = self.day.feed("m42")
        finish = feed.finish

        async def held_open() -> None:
            await self.released.wait()
            await finish()

        feed.finish = held_open  # type: ignore[method-assign]

    def held(self) -> list[TenantItemEntry]:
        return [
            e
            for e in self.day.feed("m42").entries
            if isinstance(e, TenantItemEntry) and e.state == "pending_approval"
        ]


@pytest.fixture
def paused() -> Iterator[tuple[TestClient, Paused]]:
    held = Paused()
    with TestClient(create_app(Settings(version="test"), matchday=held.day)) as client:
        assert client.post("/api/matchday", headers=STUDIO).status_code == 202
        assert client.portal is not None
        client.portal.call(wait_for_a_held_item, held)
        yield client, held
        client.portal.call(held.released.set)
        client.portal.call(held.day.wait)


async def wait_for_a_held_item(held: Paused) -> None:
    with anyio.fail_after(10):
        while not held.held():
            await anyio.sleep(0)


def path(item: TenantItemEntry) -> str:
    return (
        f"/api/tenants/{item.tenant_id}/matches/{item.match_id}/items/{item.overlay.item_id}"
        "/decision"
    )


def test_an_approval_puts_the_item_on_air_signed_by_the_editor(
    paused: tuple[TestClient, Paused],
) -> None:
    client, held = paused
    item = held.held()[0]

    answer = client.post(path(item), json={"decision": "approved"}, headers=STUDIO)

    assert answer.status_code == 200, answer.json()
    assert answer.headers["cache-control"] == "no-store"
    entry = parse_feed_entry(answer.json())
    assert isinstance(entry, TenantItemEntry)
    assert entry.state == "on_air"
    assert entry.approval is not None
    assert entry.approval.editor == "T. Ibarra"
    assert held.day.feed("m42").entries[-1] == entry


def test_a_rejection_keeps_the_reason(paused: tuple[TestClient, Paused]) -> None:
    client, held = paused
    item = held.held()[0]

    answer = client.post(
        path(item), json={"decision": "rejected", "reason": "Not our tone"}, headers=STUDIO
    )

    assert answer.status_code == 200
    assert answer.json()["approval"]["reason"] == "Not our tone"


def test_an_item_already_decided_is_a_conflict(paused: tuple[TestClient, Paused]) -> None:
    client, held = paused
    item = held.held()[0]
    client.post(path(item), json={"decision": "approved"}, headers=STUDIO)

    again = client.post(path(item), json={"decision": "approved"}, headers=STUDIO)

    assert again.status_code == 409
    assert again.json()["detail"] == "this item is not awaiting a decision"


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "maybe"},
        {"decision": "rejected"},
        {"decision": "rejected", "reason": "x" * 201},
        {"decision": "approved", "editor": "Someone Else"},
        {},
    ],
)
def test_a_malformed_decision_is_refused(
    paused: tuple[TestClient, Paused], body: dict[str, object]
) -> None:
    client, held = paused

    assert client.post(path(held.held()[0]), json=body, headers=STUDIO).status_code in (409, 422)
    assert held.held()


@pytest.mark.parametrize(
    "headers",
    [{}, {**STUDIO, "Origin": "https://elsewhere.example"}],
)
def test_decisions_come_only_from_the_studio(
    paused: tuple[TestClient, Paused], headers: dict[str, str]
) -> None:
    client, held = paused

    answer = client.post(path(held.held()[0]), json={"decision": "approved"}, headers=headers)

    assert answer.status_code == 403
    assert held.held()


@pytest.mark.parametrize(
    "where",
    [
        "/api/tenants/tribuna-austral/matches/m42/items/it-tribuna-austral-nothing/decision",
        "/api/tenants/nobody/matches/m42/items/it-nobody-x/decision",
        "/api/tenants/tribuna-austral/matches/m99/items/it-tribuna-austral-x/decision",
    ],
)
def test_unknown_items_partners_and_matches_are_not_found(
    paused: tuple[TestClient, Paused], where: str
) -> None:
    client, _ = paused

    assert client.post(where, json={"decision": "approved"}, headers=STUDIO).status_code == 404


def test_a_malformed_item_id_is_refused(paused: tuple[TestClient, Paused]) -> None:
    client, _ = paused
    where = "/api/tenants/tribuna-austral/matches/m42/items/<script>/decision"

    assert client.post(where, json={"decision": "approved"}, headers=STUDIO).status_code == 422
