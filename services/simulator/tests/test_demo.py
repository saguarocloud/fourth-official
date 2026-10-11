"""The fixed demo matchday: three matches, fixed seeds, scripted storylines, committed truth."""

import json
from functools import cache
from pathlib import Path

import pytest

from fourth_official_contracts import (
    CardEvent,
    EventAmended,
    EventVoided,
    GoalEvent,
    SaveEvent,
    parse_ground_truth,
)
from fourth_official_simulator.demo import (
    GROUND_TRUTH_DIR,
    demo_matchday,
    main,
    write_ground_truth,
)
from fourth_official_simulator.engine import SimulatedMatch, play


@cache
def played() -> dict[str, SimulatedMatch]:
    return {s.match_id: play(s) for s in demo_matchday()}


def scored(match: SimulatedMatch) -> list[tuple[str, int]]:
    return [(g.team_id, g.clock.minute) for g in match.events if isinstance(g, GoalEvent)]


def test_the_matchday_is_three_fixed_matches() -> None:
    fixtures = [(s.match_id, s.seed, s.home.squad.club, s.away.squad.club) for s in demo_matchday()]

    assert fixtures == [
        ("m42", 4207, "HCY", "NGT"),
        ("m43", 1311, "KBA", "ASV"),
        ("m44", 2718, "CAL", "WMR"),
    ]
    assert demo_matchday() == demo_matchday()


def test_the_featured_match_follows_its_script() -> None:
    match = played()["m42"]
    kinds = [t.kind for t in match.ground_truth.storylines]

    assert scored(match) == [("HCY", 12), ("HCY", 67), ("NGT", 78), ("HCY", 89)]
    assert kinds == [
        "goal",
        "pressing_collapse",
        "goal",
        "var_overturn",
        "goal",
        "goal",
        "scorer_reassigned",
    ]
    assert [type(c) for c in match.corrections] == [EventVoided, EventAmended]
    final = match.ground_truth.final_score
    assert (final.home, final.away) == (2, 1)


def test_ten_men_come_back_in_the_second_match() -> None:
    match = played()["m43"]
    reds = [
        (e.team_id, e.clock.minute)
        for e in match.events
        if isinstance(e, CardEvent) and e.card == "red"
    ]

    assert reds == [("KBA", 38)]
    assert scored(match) == [("ASV", 52), ("KBA", 81), ("KBA", 88)]
    assert "tactical_shift" in [t.kind for t in match.ground_truth.storylines]
    assert match.corrections == ()


def test_the_third_match_is_goalless_with_busy_goalkeepers() -> None:
    match = played()["m44"]
    saves = [e for e in match.events if isinstance(e, SaveEvent)]

    assert scored(match) == []
    assert {s.team_id for s in saves} == {"CAL", "WMR"}
    assert len(saves) >= 8
    assert match.corrections == ()


def test_committed_ground_truth_matches_the_simulator() -> None:
    for match_id, match in played().items():
        committed = parse_ground_truth(
            json.loads((GROUND_TRUTH_DIR / f"{match_id}.json").read_text())
        )
        assert committed == match.ground_truth, f"{match_id} is stale: run `make demo-truth`"


def test_writing_ground_truth_produces_stable_files(tmp_path: Path) -> None:
    written = write_ground_truth(tmp_path)

    assert sorted(p.name for p in written) == ["m42.json", "m43.json", "m44.json"]
    for path in written:
        text = path.read_text()
        assert text.endswith("}\n")
        assert parse_ground_truth(json.loads(text)) == played()[path.stem].ground_truth


def test_the_command_line_writes_to_the_requested_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["--out", str(tmp_path)])

    assert sorted(p.name for p in tmp_path.iterdir()) == ["m42.json", "m43.json", "m44.json"]
    assert "m42.json" in capsys.readouterr().out
