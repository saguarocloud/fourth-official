"""Match context: which club is home, and which end each team attacks in each period."""

import re
from dataclasses import dataclass

from fourth_official_contracts import PITCH_LENGTH_M

_MATCH_ID = re.compile(r"^m[0-9]{1,12}$")
_CLUB = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class MatchContext:
    match_id: str
    home: str
    away: str

    def __post_init__(self) -> None:
        if not _MATCH_ID.match(self.match_id):
            raise ValueError(f"invalid match context: match id {self.match_id!r}")
        if not (_CLUB.match(self.home) and _CLUB.match(self.away)) or self.home == self.away:
            raise ValueError(f"invalid match context: clubs {self.home!r} and {self.away!r}")

    def opponent(self, team: str) -> str:
        if team not in (self.home, self.away):
            raise ValueError(f"{team} does not play in {self.match_id}")
        return self.away if team == self.home else self.home

    def attacks_high_x(self, team: str, period: int) -> bool:
        """True if the team attacks the goal at x = 105 m in this period (home does in period 1)."""
        self.opponent(team)  # refuses a club that is not playing
        return (team == self.home) == (period == 1)

    def progress(self, team: str, period: int, x: float) -> float:
        """How far up the pitch a point is for the team: 0 at its own goal line, 1 at the other."""
        fraction = x / PITCH_LENGTH_M
        return fraction if self.attacks_high_x(team, period) else 1.0 - fraction
