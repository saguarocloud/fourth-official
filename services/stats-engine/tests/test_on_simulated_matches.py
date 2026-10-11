"""Stage one into stage two: the stats engine over whole simulated matches."""

from datetime import UTC, datetime
from functools import cache

import pytest

from fourth_official_contracts import GoalEvent, MetricSnapshot, ShotEvent, parse_metric_snapshot
from fourth_official_simulator.engine import MatchSetup, TeamSetup, simulate
from fourth_official_simulator.squads import generate_squad
from fourth_official_simulator.style import TeamStyle
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import PreparedMatch, prepare
from fourth_official_stats.snapshots import snapshots_at

STYLE = TeamStyle(pressing=0.6, directness=0.5, width=0.5, tempo=0.6)
CTX = MatchContext(match_id="m42", home="HCY", away="NGT")


@cache
def played(seed: int) -> PreparedMatch:
    events = simulate(
        MatchSetup(
            match_id="m42",
            seed=seed,
            kickoff=datetime(2026, 10, 24, 14, 0, tzinfo=UTC),
            home=TeamSetup(squad=generate_squad("HCY", seed=1), formation="4-3-3", style=STYLE),
            away=TeamSetup(squad=generate_squad("NGT", seed=1), formation="4-4-2", style=STYLE),
        )
    )
    return prepare(CTX, events)


def full_time(match: PreparedMatch) -> dict[tuple[str, str, str], MetricSnapshot]:
    final = match.events[-1].seq
    return {(s.metric, s.scope, s.window): s for s in snapshots_at(match, as_of_seq=final)}


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_full_time_snapshot_is_a_valid_contract(seed: int) -> None:
    for snapshot in full_time(played(seed)).values():
        assert parse_metric_snapshot(snapshot.to_wire()) == snapshot


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_possession_shares_add_up_to_the_whole_match(seed: int) -> None:
    snaps = full_time(played(seed))
    home, away = (
        snaps[("possession", "HCY", "match")].value,
        snaps[("possession", "NGT", "match")].value,
    )

    assert home is not None
    assert away is not None
    assert home + away == pytest.approx(1.0, abs=1e-3)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_full_time_counts_agree_with_the_events(seed: int) -> None:
    match = played(seed)
    snaps = full_time(match)
    shots = [e for e in match.events if isinstance(e, ShotEvent) and e.team_id == "HCY"]

    assert snaps[("shots", "HCY", "match")].value == len(shots)
    assert snaps[("shots", "HCY", "match")].inputs == tuple(s.event_id for s in shots)


def test_expected_goals_track_actual_goals_over_many_matches() -> None:
    xg_total = goals = 0.0
    for seed in range(1, 21):
        match = played(seed)
        snaps = full_time(match)
        xg_total += sum(snaps[("xg", club, "match")].value or 0.0 for club in ("HCY", "NGT"))
        goals += sum(isinstance(e, GoalEvent) for e in match.events)

    # The engine's and the stats engine's models are independent, but both are calibrated to the
    # same public norms, so totals over 20 matches should be in the same range.
    assert 0.6 <= xg_total / goals <= 1.6
