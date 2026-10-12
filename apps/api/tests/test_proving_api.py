"""The Proving Ground in the API: the recorded scorecards and the Release Gate's verdict on them."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fourth_official_api.proving import RESULTS, proving_router
from fourth_official_contracts import parse_gate_verdict, parse_scorecard

REPO_RESULTS = Path(__file__).resolve().parents[3] / "eval" / "results"


def client(results: Path) -> TestClient:
    app = FastAPI()
    app.include_router(proving_router(results))
    return TestClient(app)


def copied(tmp_path: Path) -> Path:
    for name in RESULTS.values():
        shutil.copy(REPO_RESULTS / name, tmp_path / name)
    return tmp_path


def test_the_recorded_runs_and_the_gates_verdict_on_them(tmp_path: Path) -> None:
    response = client(copied(tmp_path)).get("/api/proving-ground")

    assert response.status_code == 200
    body = response.json()
    assert parse_scorecard(body["baseline"]).configuration.name == "production"
    assert parse_scorecard(body["candidate"]).configuration.analyst_prompt == "analyst/v1.4"
    assert parse_scorecard(body["benchmark"]).matches == 100
    verdict = parse_gate_verdict(body["verdict"])
    assert not verdict.allowed
    assert {c.rule for c in verdict.checks if not c.passed} == {"model_written"}
    assert "max-age" in response.headers["cache-control"]


def test_the_scorecards_are_read_once_not_on_every_request(tmp_path: Path) -> None:
    results = copied(tmp_path)
    api = client(results)
    first = api.get("/api/proving-ground").json()
    (results / RESULTS["baseline"]).write_text("{}")

    assert api.get("/api/proving-ground").json() == first


def test_missing_results_are_unavailable_not_an_error(tmp_path: Path) -> None:
    response = client(tmp_path / "nowhere").get("/api/proving-ground")

    assert response.status_code == 503
    assert response.json() == {"detail": "The Proving Ground's results are not available."}


@pytest.mark.parametrize("content", ["{not json", json.dumps({"matches": 3})])
def test_a_damaged_scorecard_is_unavailable_and_says_nothing_of_its_content(
    tmp_path: Path, content: str
) -> None:
    results = copied(tmp_path)
    (results / RESULTS["candidate"]).write_text(content)

    response = client(results).get("/api/proving-ground")

    assert response.status_code == 503
    assert "matches" not in response.text
