"""The wall API: the Control Room's matches, latest items and latest correction, from the feeds."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from fourth_official_api.explainers import partners_for
from fourth_official_api.main import create_app
from fourth_official_api.settings import Settings
from fourth_official_contracts import Moment, parse_matchday_wall
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


def test_before_the_matchday_every_match_is_nil_nil_without_a_clock(client: TestClient) -> None:
    response = client.get("/api/wall")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    wall = parse_matchday_wall(response.json())
    assert {m.match_id for m in wall.matches} == set(demo_store().match_ids())
    assert all(m.state == "idle" and m.clock is None for m in wall.matches)
    assert wall.activity == ()
    assert wall.latest_correction is None


def test_after_a_run_the_wall_shows_scores_items_and_the_latest_correction(
    client: TestClient,
) -> None:
    assert client.post("/api/matchday", headers=START).status_code == 202
    assert client.portal is not None
    day: Matchday = client.app.state.matchday  # type: ignore[attr-defined]
    client.portal.call(day.wait)

    wall = parse_matchday_wall(client.get("/api/wall").json())

    assert {m.state for m in wall.matches} == {"finished"}
    assert all(m.clock is not None and m.items > 0 for m in wall.matches)
    assert 0 < len(wall.activity) <= 12
    assert wall.latest_correction is not None
