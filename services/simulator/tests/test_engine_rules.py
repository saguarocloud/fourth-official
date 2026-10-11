"""Football rules the engine must respect in every match: restarts, substitutions, possession,
continuity of play and time."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import timedelta
from functools import cache

import pytest

from fourth_official_contracts import (
    CardEvent,
    CarryEvent,
    FoulEvent,
    GoalEvent,
    MatchEvent,
    PassEvent,
    PeriodEndEvent,
    PeriodStartEvent,
    PossessionChangeEvent,
    SetPieceEvent,
    ShotEvent,
    SubstitutionEvent,
)
from fourth_official_simulator.engine import simulate
from fourth_official_simulator.pitch import Zone, pitch_to_attacking, zone_of
from matches import setup

SEEDS = range(4300, 4340)
ON_BALL = (PassEvent, CarryEvent, ShotEvent, SetPieceEvent)


@cache
def match(seed: int) -> tuple[MatchEvent, ...]:
    return simulate(setup(seed))


def _home(event: MatchEvent) -> bool:
    return getattr(event, "team_id", None) == "HCY"


def _player_refs(event: MatchEvent) -> set[str]:
    data = event.model_dump()
    return {
        v
        for k, v in data.items()
        if k.endswith("_id") and isinstance(v, str) and "-" in v and len(v) == 6
    }


# --- Restarts -------------------------------------------------------------------------------------
def test_no_free_kick_is_ever_awarded_inside_the_attacking_box() -> None:
    for seed in SEEDS:
        for event in match(seed):
            if isinstance(event, SetPieceEvent) and event.kind == "free_kick":
                progress, lateral = pitch_to_attacking(
                    event.at.x, event.at.y, home=_home(event), period=event.clock.period
                )
                assert zone_of(progress, lateral) is not Zone.BOX, (seed, event.event_id)


def test_fouls_in_the_box_give_penalties_that_mostly_score() -> None:
    penalties = scored = 0
    for seed in range(4300, 4400):
        events = match(seed)
        for i, event in enumerate(events):
            if isinstance(event, SetPieceEvent) and event.kind == "penalty":
                penalties += 1
                shot = next(e for e in events[i + 1 :] if isinstance(e, ShotEvent))
                scored += shot.outcome == "goal"
    assert penalties >= 10
    assert 0.6 <= scored / penalties <= 0.9


# --- Substitutions --------------------------------------------------------------------------------
def test_substitutes_are_never_substituted_again() -> None:
    for seed in SEEDS:
        came_on: set[str] = set()
        for event in match(seed):
            if isinstance(event, SubstitutionEvent):
                assert event.player_off_id not in came_on, (seed, event.event_id)
                came_on.add(event.player_on_id)


def test_substitutions_happen_at_dead_balls_and_never_take_off_the_player_on_the_ball() -> None:
    for seed in SEEDS:
        events = match(seed)
        for i, event in enumerate(events):
            if isinstance(event, SubstitutionEvent):
                restart = next(e for e in events[i + 1 :] if not isinstance(e, SubstitutionEvent))
                assert isinstance(restart, SetPieceEvent | PeriodStartEvent), (seed, event.event_id)
                if isinstance(restart, SetPieceEvent):
                    assert restart.player_id != event.player_off_id


def test_players_who_left_the_pitch_appear_in_no_later_event() -> None:
    for seed in SEEDS:
        gone: set[str] = set()
        for event in match(seed):
            assert not (_player_refs(event) & gone), (seed, event.event_id)
            if isinstance(event, SubstitutionEvent):
                gone.add(event.player_off_id)
            if isinstance(event, CardEvent) and event.card in {"red", "second_yellow"}:
                gone.add(event.player_id)


# --- Possession -----------------------------------------------------------------------------------
def test_possession_only_changes_hands_through_a_possession_change_event() -> None:
    for seed in SEEDS:
        holder: str | None = None
        for event in match(seed):
            if isinstance(event, PossessionChangeEvent):
                assert event.team_id != holder, (seed, event.event_id)
                holder = event.team_id
            elif isinstance(event, ON_BALL):
                if holder is None:
                    holder = event.team_id
                assert event.team_id == holder, (seed, event.event_id)


def test_the_receiver_of_a_completed_pass_is_the_next_player_on_the_ball() -> None:
    for seed in SEEDS:
        events = match(seed)
        for i, event in enumerate(events):
            if not (isinstance(event, PassEvent) and event.outcome == "complete"):
                continue
            nxt = next(
                (
                    e
                    for e in events[i + 1 :]
                    if isinstance(e, (*ON_BALL, PossessionChangeEvent, FoulEvent))
                ),
                None,
            )
            if isinstance(nxt, PassEvent | CarryEvent | ShotEvent):
                assert nxt.player_id == event.receiver_id, (seed, event.event_id)


def test_shots_are_struck_where_the_previous_action_left_the_ball() -> None:
    for seed in SEEDS:
        events = match(seed)
        for i, event in enumerate(events):
            if not isinstance(event, ShotEvent):
                continue
            before = next((e for e in reversed(events[:i]) if isinstance(e, ON_BALL)), None)
            if isinstance(before, PassEvent | CarryEvent):
                assert abs(before.end.x - event.origin.x) < 0.6, (seed, event.event_id)
                assert abs(before.end.y - event.origin.y) < 0.6, (seed, event.event_id)


def _assisting_pass(events: tuple[MatchEvent, ...], shot: ShotEvent) -> PassEvent | None:
    """The completed pass that set the shooter up, allowing one dribble by the shooter between."""
    dribbles = 0
    for event in reversed(events[: events.index(shot)]):
        if isinstance(event, CarryEvent) and event.player_id == shot.player_id and dribbles == 0:
            dribbles += 1
            continue
        if isinstance(event, (*ON_BALL, PossessionChangeEvent, FoulEvent)):
            completed_to_shooter = (
                isinstance(event, PassEvent)
                and event.outcome == "complete"
                and event.receiver_id == shot.player_id
            )
            return event if completed_to_shooter and isinstance(event, PassEvent) else None
    return None


def test_goals_credit_the_pass_that_set_the_scorer_up() -> None:
    assisted = goals = 0
    for seed in SEEDS:
        events = match(seed)
        by_id = {e.event_id: e for e in events}
        for goal in (e for e in events if isinstance(e, GoalEvent) and e.shot_event_id):
            goals += 1
            shot = by_id[goal.shot_event_id or ""]
            assert isinstance(shot, ShotEvent)
            setup_pass = _assisting_pass(events, shot)
            assert goal.assist_id == (setup_pass.player_id if setup_pass else None), (
                seed,
                goal.event_id,
            )
            assisted += goal.assist_id is not None
    # Roughly three in four top-flight goals are assisted.
    assert 0.6 <= assisted / goals <= 0.9


# --- Time -----------------------------------------------------------------------------------------
def test_half_time_lasts_fifteen_minutes() -> None:
    for seed in SEEDS:
        events = match(seed)
        end = next(e for e in events if isinstance(e, PeriodEndEvent))
        start = next(e for e in events if isinstance(e, PeriodStartEvent) and e.clock.period == 2)
        assert start.wall_clock - end.wall_clock == timedelta(minutes=15)


# --- Determinism across processes -----------------------------------------------------------------
FINGERPRINT_SCRIPT = """
import hashlib, json, sys
sys.path.insert(0, {tests!r})
from matches import setup
from fourth_official_simulator.engine import simulate
wire = json.dumps([e.to_wire() for e in simulate(setup(4207))], sort_keys=True)
print(hashlib.sha256(wire.encode()).hexdigest())
"""


def fingerprint() -> str:
    wire = json.dumps([e.to_wire() for e in simulate(setup(4207))], sort_keys=True)
    return hashlib.sha256(wire.encode()).hexdigest()


@pytest.mark.parametrize("hash_seed", ["0", "1234"])
def test_a_match_is_identical_in_a_fresh_process_with_a_different_hash_seed(hash_seed: str) -> None:
    tests = os.path.dirname(__file__)
    result = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", FINGERPRINT_SCRIPT.format(tests=tests)],
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == fingerprint()
