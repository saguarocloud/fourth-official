"""Shared match setups for engine tests."""

from datetime import UTC, datetime

from fourth_official_simulator.engine import MatchSetup, TeamSetup
from fourth_official_simulator.squads import generate_squad
from fourth_official_simulator.style import TeamStyle

KICKOFF = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)
PRESSING = TeamStyle(pressing=0.75, directness=0.4, width=0.6, tempo=0.65)
BALANCED = TeamStyle(pressing=0.5, directness=0.5, width=0.5, tempo=0.5)


def setup(
    seed: int = 4207,
    match_id: str = "m42",
    home_style: TeamStyle = PRESSING,
    away_style: TeamStyle = BALANCED,
) -> MatchSetup:
    return MatchSetup(
        match_id=match_id,
        seed=seed,
        kickoff=KICKOFF,
        home=TeamSetup(squad=generate_squad("HCY", seed=1), formation="4-3-3", style=home_style),
        away=TeamSetup(squad=generate_squad("NGT", seed=1), formation="4-2-3-1", style=away_style),
    )
