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


@pytest.mark.parametrize(
    ("content", "why"),
    [
        (None, "missing"),
        ("{not json", "not JSON"),
        ('{"matches": 3}', "not a scorecard"),
        ("[" * 5000 + "]" * 5000, "nested too deep"),
    ],
)
def test_a_scorecard_that_cannot_be_read_is_an_error_not_a_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str | None, why: str
) -> None:
    good = run(tmp_path)
    bad = tmp_path / "bad.json"
    if content is not None:
        bad.write_text(content)

    with pytest.raises(SystemExit) as stopped:
        main(["gate", "--candidate", str(bad), "--baseline", str(good)])

    assert stopped.value.code == 2, why
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert err.startswith("Release Gate: cannot read")


def test_an_oversized_scorecard_is_refused_unread(tmp_path: Path) -> None:
    good = run(tmp_path)
    huge = tmp_path / "huge.json"
    huge.write_text(" " * (2 * 1024 * 1024) + "{}")

    with pytest.raises(SystemExit) as stopped:
        main(["gate", "--candidate", str(huge), "--baseline", str(good)])

    assert stopped.value.code == 2


def test_scorecards_of_different_benchmarks_are_an_error_not_a_block(tmp_path: Path) -> None:
    one = run(tmp_path, "one.json", matches=1)
    two = run(tmp_path, "two.json", matches=2)

    with pytest.raises(SystemExit) as stopped:
        main(["gate", "--candidate", str(one), "--baseline", str(two)])

    assert stopped.value.code == 2


def test_a_run_can_be_named_for_the_gate(tmp_path: Path) -> None:
    out = tmp_path / "named.json"
    main(
        ["run", "--config", "template", "--matches", "1", "--name", "candidate", "--out", str(out)]
    )

    assert parse_scorecard(json.loads(out.read_text())).configuration.name == "candidate"


def test_a_model_run_without_foundry_is_an_error_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FOUNDRY_PROJECT_ENDPOINT", raising=False)

    with pytest.raises(SystemExit) as stopped:
        main(["run", "--config", "production", "--matches", "1", "--out", str(tmp_path / "p.json")])

    assert stopped.value.code == 2


def test_the_summary_tabulates_the_scorecard_and_the_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    card = run(tmp_path, "candidate.json")
    verdict = str(tmp_path / "verdict.json")
    main(["gate", "--candidate", str(card), "--baseline", str(card), "--out", verdict])
    capsys.readouterr()

    main(["summary", "--dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert out.startswith("## Release Gate: template is allowed")
    assert "| Supported claims |" in out
    assert "| pass | verifier_catch |" in out


def test_the_summary_never_repeats_claim_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    card = run(tmp_path, "candidate.json")
    wire = json.loads(card.read_text())
    wire["failures"] = [
        {
            "matchId": "m1001",
            "itemId": "it-northlight-sport-in-m1001-goal-HCY-s0287-a1-v1",
            "claimId": "cl-1",
            "text": "| injected | [link](https://evil.example) |",
            "eventIds": ["m1001-e0287"],
            "reasons": ["names minute 3, when none of its events happened"],
        }
    ]
    card.write_text(json.dumps(wire))

    main(["summary", "--dir", str(tmp_path)])

    out = capsys.readouterr().out
    assert "evil.example" not in out
    assert "1 failed claim listed in the scorecard artifact." in out


def test_a_summary_without_a_scorecard_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["summary", "--dir", str(tmp_path)])

    assert "No scorecard was produced" in capsys.readouterr().out


def test_a_summary_says_why_a_run_was_not_gated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, "candidate.json")

    main(["summary", "--dir", str(tmp_path)])
    without_baseline = capsys.readouterr().out
    (tmp_path / "baseline.json").write_text("{}")
    main(["summary", "--dir", str(tmp_path)])
    without_verdict = capsys.readouterr().out

    assert "not gated: the base branch has no production configuration yet" in without_baseline
    assert "the gate could not judge" in without_verdict
