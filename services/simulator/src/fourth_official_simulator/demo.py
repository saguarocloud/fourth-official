"""The fixed demo matchday: three matches with fixed seeds and scripted storylines.

Every demo run plays exactly these matches, so moments, corrections and ground truth are the same
each time. Their ground truth is committed under `eval/ground-truth/`; regenerate it with
`make demo-truth` after changing the simulator.
"""

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from fourth_official_simulator.engine import MatchSetup, TeamSetup, play
from fourth_official_simulator.squads import generate_squad
from fourth_official_simulator.storylines import (
    RedCard,
    ScorerReassigned,
    ScriptedGoal,
    Storyline,
    StyleShift,
    VarVoid,
)
from fourth_official_simulator.style import TeamStyle

GROUND_TRUTH_DIR = Path(__file__).resolve().parents[4] / "eval" / "ground-truth"
SQUAD_SEED = 2026
KICKOFF = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)

FEATURED = Storyline(
    name="Early lead, the press collapses, a goal ruled out, a late winner reassigned",
    natural_goals=False,
    directives=(
        ScriptedGoal(club="HCY", minute=12),
        StyleShift(club="NGT", minute=61, label="NGT press collapses", pressing=0.15, tempo=0.35),
        ScriptedGoal(club="HCY", minute=67),
        VarVoid(club="HCY", goal_minute=67, reason="VAR_OFFSIDE"),
        ScriptedGoal(club="NGT", minute=78),
        ScriptedGoal(club="HCY", minute=89),
        ScorerReassigned(club="HCY", goal_minute=89),
    ),
)
TEN_MEN = Storyline(
    name="Down to ten, a switch to direct play, a late comeback",
    natural_goals=False,
    directives=(
        RedCard(club="KBA", minute=38),
        StyleShift(
            club="KBA",
            minute=40,
            label="KBA go direct with ten men",
            directness=0.8,
            width=0.35,
        ),
        ScriptedGoal(club="ASV", minute=52),
        ScriptedGoal(club="KBA", minute=81),
        ScriptedGoal(club="KBA", minute=88),
    ),
)
CHAOS = Storyline(
    name="Goalless chaos and goalkeeper heroics",
    natural_goals=False,
    directives=(),
)


def _team(club: str, formation: str, style: TeamStyle) -> TeamSetup:
    return TeamSetup(squad=generate_squad(club, seed=SQUAD_SEED), formation=formation, style=style)


def _match(
    match_id: str, seed: int, *, home: TeamSetup, away: TeamSetup, storyline: Storyline
) -> MatchSetup:
    return MatchSetup(
        match_id=match_id, seed=seed, kickoff=KICKOFF, home=home, away=away, storyline=storyline
    )


def demo_matchday() -> tuple[MatchSetup, ...]:
    """The featured match first, then the two others."""
    return (
        _match(
            "m42",
            4207,
            home=_team(
                "HCY", "4-3-3", TeamStyle(pressing=0.6, directness=0.5, width=0.6, tempo=0.6)
            ),
            away=_team(
                "NGT", "4-2-3-1", TeamStyle(pressing=0.85, directness=0.45, width=0.5, tempo=0.65)
            ),
            storyline=FEATURED,
        ),
        _match(
            "m43",
            1311,
            home=_team(
                "KBA", "4-4-2", TeamStyle(pressing=0.55, directness=0.45, width=0.6, tempo=0.5)
            ),
            away=_team(
                "ASV", "4-3-3", TeamStyle(pressing=0.5, directness=0.5, width=0.5, tempo=0.55)
            ),
            storyline=TEN_MEN,
        ),
        _match(
            "m44",
            2718,
            home=_team(
                "CAL", "4-4-2", TeamStyle(pressing=0.8, directness=0.75, width=0.6, tempo=0.85)
            ),
            away=_team(
                "WMR", "3-5-2", TeamStyle(pressing=0.8, directness=0.7, width=0.55, tempo=0.85)
            ),
            storyline=CHAOS,
        ),
    )


def write_ground_truth(directory: Path = GROUND_TRUTH_DIR) -> list[Path]:
    """Write each demo match's ground truth as stable, pretty-printed JSON; returns the files."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for setup in demo_matchday():
        path = directory / f"{setup.match_id}.json"
        truth = play(setup).ground_truth.to_wire()
        path.write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write the demo matchday's ground truth.")
    parser.add_argument("--out", type=Path, default=GROUND_TRUTH_DIR, help="output directory")
    args = parser.parse_args(argv)
    for path in write_ground_truth(args.out):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
