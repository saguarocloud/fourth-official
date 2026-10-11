"""Each partner reads its own feed: the shared clock and corrections, and its own items only."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fourth_official_api.main import create_app
from fourth_official_api.settings import Settings
from fourth_official_contracts import parse_feed_entry
from fourth_official_match_data import demo_store
from fourth_official_replay import Matchday, ReplayConfig
from test_partners import no_wait, partners, template_only

PARTNERS = ("northlight-sport", "tribuna-austral", "rheinblick-sport")
START = {"X-Requested-By": "fourth-official"}


def finish(client: TestClient) -> None:
    """Wait for the run on the app's own event loop."""
    assert client.portal is not None
    day: Matchday = client.app.state.matchday  # type: ignore[attr-defined]
    client.portal.call(day.wait)


@pytest.fixture
def client() -> Iterator[TestClient]:
    day = Matchday(
        demo_store(),
        template_only,
        config=ReplayConfig(),
        cooldown=600.0,
        sleep=no_wait,
        partners=partners,
    )
    with TestClient(create_app(Settings(version="test"), matchday=day)) as client:
        assert client.post("/api/matchday", headers=START).status_code == 202
        finish(client)
        yield client


def test_the_partners_are_listed_with_their_policy_and_editor(client: TestClient) -> None:
    response = client.get("/api/tenants")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "tenants": [
            {
                "tenantId": "northlight-sport",
                "displayName": "Northlight Sport",
                "locale": "en-GB",
                "disclosureMode": "label-unless-approved",
                "approvalRequired": ["recap"],
                "dutyEditor": "R. Hale",
            },
            {
                "tenantId": "rheinblick-sport",
                "displayName": "Rheinblick Sport",
                "locale": "de-DE",
                "disclosureMode": "eu-strict",
                "approvalRequired": ["recap"],
                "dutyEditor": "L. Vogt",
            },
            {
                "tenantId": "tribuna-austral",
                "displayName": "Tribuna Austral",
                "locale": "es-MX",
                "disclosureMode": "label-all",
                "approvalRequired": ["insight", "recap"],
                "dutyEditor": "T. Ibarra",
            },
        ]
    }


@pytest.mark.parametrize("tenant", PARTNERS)
def test_a_partner_s_feed_holds_only_its_items_and_the_shared_facts(
    client: TestClient, tenant: str
) -> None:
    body = client.get(f"/api/tenants/{tenant}/matches/m42/feed").json()
    entries = [parse_feed_entry(e) for e in body["entries"]]

    kinds = {e.kind for e in entries}
    assert kinds <= {"clock", "correction", "tenant_item"}
    assert "tenant_item" in kinds
    assert {e.tenant_id for e in entries if e.kind == "tenant_item"} == {tenant}
    assert body["finished"] is True


def test_a_partner_s_stream_holds_only_its_items(client: TestClient) -> None:
    with client.stream("GET", "/api/tenants/tribuna-austral/matches/m42/stream") as stream:
        text = "".join(stream.iter_text())

    assert "event: tenant_item" in text
    assert "northlight-sport" not in text
    assert "rheinblick-sport" not in text
    assert "event: insight" not in text
    assert text.rstrip().endswith('"generation": 1}')


@pytest.mark.parametrize(
    "path",
    [
        "/api/tenants/evil-sport/matches/m42/feed",
        "/api/tenants/northlight-sport/matches/m99/feed",
        "/api/tenants/evil-sport/matches/m42/stream",
    ],
)
def test_unknown_partners_and_matches_are_not_found(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_a_malformed_partner_id_is_refused(client: TestClient) -> None:
    assert client.get("/api/tenants/Evil..Sport/matches/m42/feed").status_code == 422


def test_a_partner_feed_gives_a_cursor_past_what_it_scanned(client: TestClient) -> None:
    body = client.get("/api/tenants/tribuna-austral/matches/m42/feed?after=0").json()
    every = client.get("/api/matches/m42/feed?after=0").json()

    assert body["cursor"] == every["entries"][-1]["entrySeq"]
