"""The Proving Ground from the command line: run a configuration, then gate a candidate."""

import json
from pathlib import Path

import pytest

from fourth_official_contracts import parse_gate_verdict, parse_scorecard
from fourth_official_proving.__main__ import main


def run(tmp_path: Path, name: str = "card.json", matches: int = 2) -> Path:
    out = tmp_path / name
    main(["run", "--config", "template", "--matches", str(matches), "--out", str(out)])
    return out


def test_a_run_writes_its_scorecard(tmp_path: Path) -> None:
    card = parse_scorecard(json.loads(run(tmp_path).read_text()))

    assert card.configuration.name == "template"
    assert (card.matches, card.first_match) == (2, "m1001")
    assert card.metrics.supported_claims.of > 0
    assert card.metrics.verifier_catch.hit == card.metrics.verifier_catch.of


def test_an_unknown_configuration_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["run", "--config", "nope", "--matches", "1", "--out", str(tmp_path / "x.json")])


def test_the_gate_allows_a_candidate_as_good_as_its_baseline(tmp_path: Path) -> None:
    card = run(tmp_path)
    verdict = tmp_path / "verdict.json"

    main(["gate", "--candidate", str(card), "--baseline", str(card), "--out", str(verdict)])

    assert parse_gate_verdict(json.loads(verdict.read_text())).allowed


def test_the_gate_exits_non_zero_when_it_blocks(tmp_path: Path) -> None:
    baseline = run(tmp_path)
    wire = json.loads(baseline.read_text())
    claims = wire["metrics"]["supportedClaims"]
    wire["metrics"]["supportedClaims"] = {"hit": claims["of"] - 1, "of": claims["of"]}
    wire["configuration"]["name"] = "candidate"
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(wire))

    with pytest.raises(SystemExit) as stopped:
        main(["gate", "--candidate", str(candidate), "--baseline", str(baseline)])

    assert stopped.value.code == 1
