"""Policy Studio in the API: read every partner's policy and its history, edit it from the
studio's own pages, and reset it to the release's. Edits govern the next item (the pipeline
reads the book at every item) and are kept with who, when and why."""

from collections.abc import Iterator
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from fourth_official_api.main import create_app
from fourth_official_api.settings import Settings
from fourth_official_contracts import parse_policy_history

STUDIO = {"X-Requested-By": "fourth-official"}
RHEINBLICK = "rheinblick-sport"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(version="test"))) as api:
        yield api


def current(client: TestClient, tenant: str = RHEINBLICK) -> dict[str, Any]:
    history = client.get(f"/api/policies/{tenant}").json()
    policy: dict[str, Any] = history["versions"][-1]
    return policy


def edit(client: TestClient, policy: dict[str, Any], **body: object) -> httpx2.Response:
    payload = {"policy": policy, "baseVersion": policy["version"], "reason": "Tighter"} | body
    return client.post(f"/api/policies/{RHEINBLICK}", json=payload, headers=STUDIO)


def test_every_partner_s_policy_is_listed_with_its_version(client: TestClient) -> None:
    answer = client.get("/api/policies")

    assert answer.status_code == 200
    listed = answer.json()["policies"]
    assert [p["tenantId"] for p in listed] == [
        "northlight-sport",
        "rheinblick-sport",
        "tribuna-austral",
    ]
    assert all(p["version"] == 1 for p in listed)
    assert answer.headers["cache-control"] == "no-store"


def test_a_partner_s_history_holds_every_version_and_change(client: TestClient) -> None:
    history = parse_policy_history(client.get(f"/api/policies/{RHEINBLICK}").json())

    assert history.current.tenant_id == RHEINBLICK
    assert history.changes[0].action == "bundled"


def test_an_unknown_partner_is_not_found(client: TestClient) -> None:
    assert client.get("/api/policies/nobody").status_code == 404


def test_an_edit_is_kept_and_governs_what_the_api_reports(client: TestClient) -> None:
    policy = current(client) | {"approvalRequired": ["recap", "insight"]}

    answer = edit(client, policy)

    assert answer.status_code == 200, answer.json()
    assert answer.json()["version"] == 2
    assert answer.json()["fields"] == ["approvalRequired"]
    assert answer.json()["editor"] == "L. Vogt"
    partner = next(
        t for t in client.get("/api/tenants").json()["tenants"] if t["tenantId"] == RHEINBLICK
    )
    assert partner["approvalRequired"] == ["recap", "insight"]


def test_raw_yaml_is_accepted_too(client: TestClient) -> None:
    policy = current(client)
    text = "\n".join(
        f"{key}: {value if not isinstance(value, list) else '[' + ', '.join(value) + ']'}"
        for key, value in (policy | {"latencyBudgetMs": 6000}).items()
    )

    answer = client.post(
        f"/api/policies/{RHEINBLICK}",
        json={"yaml": text, "baseVersion": 1, "reason": "From the raw view"},
        headers=STUDIO,
    )

    assert answer.status_code == 200, answer.json()
    assert answer.json()["fields"] == ["latencyBudgetMs"]


def test_an_invalid_policy_is_refused_with_the_reason_in_words(client: TestClient) -> None:
    answer = edit(client, current(client) | {"maxItemsPerMinute": 99})

    assert answer.status_code == 422
    assert "maxItemsPerMinute" in answer.json()["detail"]
    assert current(client)["version"] == 1


def test_an_edit_on_an_old_version_is_a_conflict(client: TestClient) -> None:
    first = current(client)
    assert edit(client, first | {"latencyBudgetMs": 6000}).status_code == 200

    answer = edit(client, first | {"latencyBudgetMs": 7000})

    assert answer.status_code == 409
    assert "version 2" in answer.json()["detail"]


def test_an_edit_that_changes_nothing_is_refused(client: TestClient) -> None:
    answer = edit(client, current(client))

    assert answer.status_code == 422
    assert answer.json()["detail"] == "The edit changes nothing"


@pytest.mark.parametrize(
    "body",
    [
        {"baseVersion": 1, "reason": "x"},
        {"policy": {}, "yaml": "x", "baseVersion": 1, "reason": "x"},
        {"policy": {}, "baseVersion": 1, "reason": ""},
        {"policy": {}, "baseVersion": 1, "reason": "two\nlines"},
        {"yaml": "x" * 70_000, "baseVersion": 1, "reason": "big"},
    ],
)
def test_a_malformed_edit_is_refused(client: TestClient, body: dict[str, Any]) -> None:
    answer = client.post(f"/api/policies/{RHEINBLICK}", json=body, headers=STUDIO)

    assert answer.status_code == 422


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Requested-By": "someone"}, {**STUDIO, "Origin": "https://evil.example"}],
)
def test_edits_come_only_from_the_studio_s_own_pages(
    client: TestClient, headers: dict[str, str]
) -> None:
    policy = current(client) | {"latencyBudgetMs": 6000}
    payload = {"policy": policy, "baseVersion": 1, "reason": "x"}

    answer = client.post(f"/api/policies/{RHEINBLICK}", json=payload, headers=headers)

    assert answer.status_code == 403
    assert current(client)["version"] == 1


def test_reset_brings_back_the_release_s_policies(client: TestClient) -> None:
    edit(client, current(client) | {"maxItemsPerMinute": 2})

    answer = client.post("/api/policies/reset", json={"reason": "End of the demo"}, headers=STUDIO)

    assert answer.status_code == 200
    (change,) = answer.json()["changes"]
    assert (change["tenantId"], change["action"], change["version"]) == (RHEINBLICK, "reset", 3)
    assert current(client)["maxItemsPerMinute"] == 4


def test_edits_are_limited_per_minute(client: TestClient) -> None:
    statuses = []
    for budget in range(2000, 2000 + 11 * 100, 100):
        policy = current(client) | {"latencyBudgetMs": budget}
        statuses.append(edit(client, policy).status_code)

    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429
