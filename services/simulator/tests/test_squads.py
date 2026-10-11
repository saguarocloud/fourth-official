"""Fictional squads: deterministic, football-shaped, and never named after real footballers."""

from collections import Counter

import pytest

from fourth_official_simulator.names import BLOCKLIST, FIRST_NAMES, LAST_NAMES
from fourth_official_simulator.squads import (
    CLUB_CODES,
    FORMATIONS,
    Position,
    generate_squad,
    league_squads,
    starting_xi,
)

SQUAD_SIZE = 25


def test_a_squad_has_twenty_five_players_with_unique_shirts_and_matching_ids() -> None:
    squad = generate_squad("HCY", seed=7)

    assert len(squad.players) == SQUAD_SIZE
    shirts = [p.shirt for p in squad.players]
    assert len(set(shirts)) == SQUAD_SIZE
    assert all(1 <= s <= 99 for s in shirts)
    assert all(p.player_id == f"HCY-{p.shirt:02d}" for p in squad.players)


def test_a_squad_is_shaped_like_a_real_one() -> None:
    counts = Counter(p.position for p in generate_squad("NGT", seed=7).players)

    assert counts[Position.GOALKEEPER] == 3
    assert counts[Position.DEFENDER] == 8
    assert counts[Position.MIDFIELDER] == 8
    assert counts[Position.FORWARD] == 6


def test_goalkeepers_wear_one_thirteen_or_a_keeper_number() -> None:
    keepers = [
        p for p in generate_squad("KBA", seed=7).players if p.position is Position.GOALKEEPER
    ]

    assert 1 in {k.shirt for k in keepers}


def test_the_same_club_and_seed_always_produce_the_same_squad() -> None:
    assert generate_squad("ASV", seed=11) == generate_squad("ASV", seed=11)


def test_different_clubs_get_different_squads() -> None:
    names_a = {p.name for p in generate_squad("CAL", seed=11).players}
    names_b = {p.name for p in generate_squad("WMR", seed=11).players}

    assert names_a.isdisjoint(names_b)


def test_the_league_has_eight_clubs_and_no_name_appears_twice() -> None:
    squads = league_squads(seed=2026)
    names = [p.name for squad in squads.values() for p in squad.players]

    assert set(squads) == set(CLUB_CODES)
    assert len(names) == len(set(names))


def test_no_generated_player_shares_a_real_footballers_name() -> None:
    blocked = {name.casefold() for name in BLOCKLIST}
    for seed in range(20):
        for squad in league_squads(seed=seed).values():
            for player in squad.players:
                assert player.name.casefold() not in blocked, player.name


def test_name_pools_never_contain_a_famous_footballers_surname() -> None:
    famous_surnames = {name.split()[-1].casefold() for name in BLOCKLIST}

    assert not famous_surnames & {last.casefold() for last in LAST_NAMES}


def test_name_pools_are_large_enough_for_a_whole_league() -> None:
    assert len(FIRST_NAMES) * len(LAST_NAMES) > 50 * 8 * SQUAD_SIZE


@pytest.mark.parametrize("formation", sorted(FORMATIONS))
def test_a_starting_eleven_fills_its_formation(formation: str) -> None:
    xi = starting_xi(generate_squad("BRM", seed=3), formation)
    counts = Counter(p.position for p in xi)
    defenders, midfielders, forwards = FORMATIONS[formation]

    assert len(xi) == 11
    assert counts[Position.GOALKEEPER] == 1
    assert (counts[Position.DEFENDER], counts[Position.MIDFIELDER], counts[Position.FORWARD]) == (
        defenders,
        midfielders,
        forwards,
    )


def test_an_unknown_formation_is_refused() -> None:
    with pytest.raises(ValueError, match="formation"):
        starting_xi(generate_squad("SLT", seed=3), "2-2-6")


def test_an_unknown_club_is_refused() -> None:
    with pytest.raises(ValueError, match="club"):
        generate_squad("XYZ", seed=3)
