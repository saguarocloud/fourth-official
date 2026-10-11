"""The detector over whole simulated matches: complete, contract-valid, incremental and quick."""

import time
from functools import cache

import pytest

from fourth_official_contracts import GoalEvent, Moment, parse_moment
from fourth_official_moments.detector import detect
from fourth_official_simulator.engine import simulate
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import PreparedMatch, prepare
from matches import setup

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")
SEEDS = range(7000, 7010)


@cache
def match(seed: int) -> PreparedMatch:
    return prepare(CTX, simulate(setup(seed)))


@cache
def moments(seed: int) -> tuple[Moment, ...]:
    return detect(match(seed))[1]


@pytest.mark.parametrize("seed", SEEDS)
def test_every_goal_is_a_moment_and_every_moment_survives_the_wire(seed: int) -> None:
    goals = [e.event_id for e in match(seed).events if isinstance(e, GoalEvent)]

    assert [m.event_ids[-1] for m in moments(seed) if m.kind == "goal"] == goals
    for moment in moments(seed):
        assert parse_moment(moment.to_wire()) == moment


def test_moments_come_in_match_order_with_unique_ids() -> None:
    for seed in SEEDS:
        found = moments(seed)
        assert [m.as_of_seq for m in found] == sorted(m.as_of_seq for m in found)
        assert len({m.moment_id for m in found}) == len(found)


def test_detecting_in_pieces_finds_exactly_what_detecting_at_once_does() -> None:
    whole = match(7000)
    state, found = None, []
    for cut in (400, 900, 1500, len(whole.events)):
        piece = prepare(CTX, whole.events[:cut])
        state, more = detect(piece, state)
        found += more

    assert tuple(found) == moments(7000)


def test_shift_moments_are_rare_in_ordinary_matches() -> None:
    # No storyline changes either side's style here, so pressing shifts are noise. Calibration
    # over 30 seeds gives about 0.07 per match (docs/moments.md).
    shifts = sum(1 for seed in SEEDS for m in moments(seed) if m.shifts)

    assert shifts / len(SEEDS) <= 0.3


def test_a_whole_match_is_detected_quickly() -> None:
    whole = match(7001)
    start = time.perf_counter()
    detect(whole)

    assert time.perf_counter() - start < 2.0
