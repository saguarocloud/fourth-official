"""The operations API: the matchday's run measured against its objectives, from the feeds."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fourth_official_api.explainers import partners_for
from fourth_official_api.main import create_app
from fourth_official_api.settings import Settings
from fourth_official_contracts import Moment, parse_operations_report
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_policy import bundled_store
from fourth_official_replay import Matchday, ReplayConfig
from fourth_official_verifier import MatchFacts

START = {"X-Requested-By": "fourth-official"}


async def no_wait(seconds: float) -> None:
    return None


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


@pytest.fixture
def client() -> Iterator[TestClient]:
    policies = [loaded.policy for loaded in bundled_store().all()]
    day = Matchday(
        demo_store(),
        template_only,
        config=ReplayConfig(),
        cooldown=600.0,
        sleep=no_wait,
        partners=partners_for(policies, None),
    )
    with TestClient(create_app(Settings(version="test"), matchday=day)) as client:
        yield client


def test_before_the_matchday_starts_every_match_is_idle_and_nothing_is_measured(
    client: TestClient,
) -> None:
    response = client.get("/api/operations")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    report = parse_operations_report(response.json())
    assert {m.state for m in report.matches} == {"idle"}
    assert {m.match_id for m in report.matches} == set(demo_store().match_ids())
    assert report.on_air.count == 0
    assert all(o.measured_ms is None for o in report.objectives)


def test_after_a_run_every_match_is_measured_for_every_partner(client: TestClient) -> None:
    assert client.post("/api/matchday", headers=START).status_code == 202
    assert client.portal is not None
    day: Matchday = client.app.state.matchday  # type: ignore[attr-defined]
    client.portal.call(day.wait)

    report = parse_operations_report(client.get("/api/operations").json())

    assert {m.state for m in report.matches} == {"finished"}
    for match in report.matches:
        assert match.events_played > 0
        assert match.fallbacks.hit == match.fallbacks.of > 0
        assert {p.tenant_id for p in match.partners} == {
            "northlight-sport",
            "tribuna-austral",
            "rheinblick-sport",
        }
    assert report.on_air.count == sum(p.on_air.count for m in report.matches for p in m.partners)
    assert report.budget.of == report.on_air.count
