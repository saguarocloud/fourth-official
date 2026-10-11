"""An editor decides on a held item: approve puts it on air, reject keeps it off with the reason.
Decisions come only from the studio's own pages, like starting the matchday."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fourth_official_api.decision_routes import _headers_of, _status_of
from fourth_official_api.main import create_app
from fourth_official_api.settings import Settings
from fourth_official_contracts import TenantItemEntry, parse_feed_entry
from fourth_official_replay.errors import (
    CorrectedSinceError,
    DecisionError,
    FullTimeError,
    NoRoomOnAirError,
    NotAwaitingError,
    ReplayedSinceError,
)
from paused import Paused

STUDIO = {"X-Requested-By": "fourth-official"}


@pytest.fixture
def paused() -> Iterator[tuple[TestClient, Paused]]:
    held = Paused()
    with TestClient(create_app(Settings(version="test"), matchday=held.day)) as client:
        assert client.post("/api/matchday", headers=STUDIO).status_code == 202
        assert client.portal is not None
        client.portal.call(held.until_held)
        yield client, held
        client.portal.call(held.released.set)
        client.portal.call(held.day.wait)


def body(held: Paused, decision: str = "approved", **extra: object) -> dict[str, object]:
    return {"decision": decision, "generation": held.generation, **extra}


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

    answer = client.post(path(item), json=body(held), headers=STUDIO)

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
        path(item), json=body(held, "rejected", reason="Not our tone"), headers=STUDIO
    )

    assert answer.status_code == 200
    assert answer.json()["approval"]["reason"] == "Not our tone"


def test_an_item_already_decided_is_a_conflict(paused: tuple[TestClient, Paused]) -> None:
    client, held = paused
    item = held.held()[0]
    client.post(path(item), json=body(held), headers=STUDIO)

    again = client.post(path(item), json=body(held), headers=STUDIO)

    assert again.status_code == 409
    assert again.json()["detail"] == "this item is not awaiting a decision"


@pytest.mark.parametrize(
    "change",
    [
        {"decision": "maybe"},
        {"decision": "rejected"},
        {"decision": "rejected", "reason": "x" * 201},
        {"decision": "rejected", "reason": "two\nlines"},
        {"decision": "rejected", "reason": "hidden\u202etext"},
        {"decision": "approved", "editor": "Someone Else"},
        {"generation": None},
    ],
)
def test_a_malformed_decision_is_refused(
    paused: tuple[TestClient, Paused], change: dict[str, object]
) -> None:
    client, held = paused
    sent = {k: v for k, v in {**body(held), **change}.items() if v is not None}

    assert client.post(path(held.held()[0]), json=sent, headers=STUDIO).status_code == 422
    assert held.held()


def test_a_reason_given_with_an_approval_is_not_kept(paused: tuple[TestClient, Paused]) -> None:
    client, held = paused

    answer = client.post(path(held.held()[0]), json=body(held, reason="Fine"), headers=STUDIO)

    assert answer.json()["approval"]["reason"] is None


def test_a_decision_made_in_an_earlier_run_is_refused(paused: tuple[TestClient, Paused]) -> None:
    client, held = paused
    stale = {**body(held), "generation": held.day.feed("m42").generation - 1}

    answer = client.post(path(held.held()[0]), json=stale, headers=STUDIO)

    assert answer.status_code == 409
    assert answer.json()["detail"] == "the matchday has been replayed since; reload to see it"
    assert held.held()


@pytest.mark.parametrize(
    "headers",
    [{}, {**STUDIO, "Origin": "https://elsewhere.example"}],
)
def test_decisions_come_only_from_the_studio(
    paused: tuple[TestClient, Paused], headers: dict[str, str]
) -> None:
    client, held = paused

    answer = client.post(path(held.held()[0]), json=body(held), headers=headers)

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
    client, held = paused

    assert client.post(where, json=body(held), headers=STUDIO).status_code == 404


def test_a_malformed_item_id_is_refused(paused: tuple[TestClient, Paused]) -> None:
    client, held = paused
    where = "/api/tenants/tribuna-austral/matches/m42/items/<script>/decision"

    assert client.post(where, json=body(held), headers=STUDIO).status_code == 422


def test_after_full_time_a_decision_is_gone(paused: tuple[TestClient, Paused]) -> None:
    client, held = paused
    item = held.held()[0]
    assert client.portal is not None
    client.portal.call(held.released.set)
    client.portal.call(held.day.wait)

    answer = client.post(path(item), json=body(held), headers=STUDIO)

    assert answer.status_code == 410
    assert answer.json()["detail"] == "the match has reached full time; held items stay off air"


@pytest.mark.parametrize(
    ("refused", "status", "retry"),
    [
        (NotAwaitingError(), 409, None),
        (ReplayedSinceError(), 409, None),
        (CorrectedSinceError(), 409, None),
        (FullTimeError(), 410, None),
        (NoRoomOnAirError(), 503, "5"),
    ],
)
def test_each_refusal_has_its_own_status(
    refused: DecisionError, status: int, retry: str | None
) -> None:
    assert _status_of(refused) == status
    assert _headers_of(refused).get("Retry-After") == retry
