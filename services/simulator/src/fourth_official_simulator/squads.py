"""Fictional squads for the Meridian League: deterministic, football-shaped, safely named."""

import random
from dataclasses import dataclass
from enum import StrEnum

from fourth_official_simulator.names import BLOCKLIST, FIRST_NAMES, LAST_NAMES

CLUB_CODES: tuple[str, ...] = ("HCY", "NGT", "KBA", "ASV", "CAL", "WMR", "BRM", "SLT")

# Formation name to (defenders, midfielders, forwards); the goalkeeper is implied.
FORMATIONS: dict[str, tuple[int, int, int]] = {
    "4-3-3": (4, 3, 3),
    "4-4-2": (4, 4, 2),
    "4-2-3-1": (4, 5, 1),
    "3-5-2": (3, 5, 2),
    "5-3-2": (5, 3, 2),
}

# Fixed salt: the surname pool is dealt out to clubs identically for every seed, so no surname
# (and therefore no full name) is ever shared between clubs.
_SURNAME_DEAL_SALT = "meridian-league-surnames"


class Position(StrEnum):
    GOALKEEPER = "GK"
    DEFENDER = "DF"
    MIDFIELDER = "MF"
    FORWARD = "FW"


# Squad shape and the shirt numbers each position conventionally wears.
_SHAPE: tuple[tuple[Position, int, tuple[int, ...]], ...] = (
    (Position.GOALKEEPER, 3, (1, 13, 31)),
    (Position.DEFENDER, 8, (2, 3, 4, 5, 6, 12, 15, 16, 26, 33)),
    (Position.MIDFIELDER, 8, (8, 10, 14, 17, 18, 20, 22, 23, 25, 27)),
    (Position.FORWARD, 6, (7, 9, 11, 19, 21, 24, 29, 30)),
)
SQUAD_SIZE = sum(count for _, count, _ in _SHAPE)


@dataclass(frozen=True, slots=True)
class Player:
    player_id: str
    shirt: int
    name: str
    position: Position


@dataclass(frozen=True, slots=True)
class Squad:
    club: str
    players: tuple[Player, ...]


def _club_surnames(club: str) -> tuple[str, ...]:
    dealt = list(LAST_NAMES)
    random.Random(_SURNAME_DEAL_SALT).shuffle(dealt)
    share = len(dealt) // len(CLUB_CODES)
    index = CLUB_CODES.index(club)
    return tuple(dealt[index * share : (index + 1) * share])


def _names(club: str, rng: random.Random) -> list[str]:
    blocked = {name.casefold() for name in BLOCKLIST}
    surnames = rng.sample(_club_surnames(club), SQUAD_SIZE)
    names = []
    for surname in surnames:
        name = f"{rng.choice(FIRST_NAMES)} {surname}"
        while name.casefold() in blocked:  # pool surnames exclude famous ones; belt and braces
            name = f"{rng.choice(FIRST_NAMES)} {surname}"
        names.append(name)
    return names


def generate_squad(club: str, seed: int) -> Squad:
    """A 25-player squad for a Meridian League club, identical for the same club and seed."""
    if club not in CLUB_CODES:
        raise ValueError(f"unknown club {club!r}; expected one of {', '.join(CLUB_CODES)}")
    rng = random.Random(f"{club}:{seed}")
    names = iter(_names(club, rng))
    players: list[Player] = []
    for position, count, shirts in _SHAPE:
        chosen = sorted([shirts[0], *rng.sample(shirts[1:], count - 1)])
        players.extend(
            Player(
                player_id=f"{club}-{shirt:02d}", shirt=shirt, name=next(names), position=position
            )
            for shirt in chosen
        )
    return Squad(club=club, players=tuple(players))


def league_squads(seed: int) -> dict[str, Squad]:
    """Every club's squad for one league season seed."""
    return {club: generate_squad(club, seed) for club in CLUB_CODES}


def starting_xi(squad: Squad, formation: str) -> tuple[Player, ...]:
    """The first-choice eleven for a formation: the lowest shirt numbers in each position."""
    if formation not in FORMATIONS:
        raise ValueError(
            f"unknown formation {formation!r}; expected one of {', '.join(FORMATIONS)}"
        )
    defenders, midfielders, forwards = FORMATIONS[formation]
    needed = {
        Position.GOALKEEPER: 1,
        Position.DEFENDER: defenders,
        Position.MIDFIELDER: midfielders,
        Position.FORWARD: forwards,
    }
    return tuple(
        player
        for position, count in needed.items()
        for player in sorted(
            (p for p in squad.players if p.position is position), key=lambda p: p.shirt
        )[:count]
    )
