"""Match event contract: what a valid event is, and which malformed events are refused."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from builders import goal, pass_, shot
from fourth_official_contracts import (
    GoalEvent,
    MatchClock,
    PassEvent,
    ShotEvent,
    parse_match_event,
)


def test_parses_a_shot_into_its_typed_model() -> None:
    event = parse_match_event(shot())

    assert isinstance(event, ShotEvent)
    assert event.clock == MatchClock(period=2, minute=67, second=12)
    assert event.wall_clock == datetime(2026, 10, 24, 15, 7, 12, 400000, tzinfo=UTC)


def test_round_trips_through_the_wire_format() -> None:
    raw = shot()

    assert parse_match_event(raw).to_wire() == raw


def test_events_are_immutable() -> None:
    event = parse_match_event(shot())

    with pytest.raises(ValidationError):
        event.seq = 999  # type: ignore[misc]


def test_parses_a_completed_pass() -> None:
    event = parse_match_event(pass_())

    assert isinstance(event, PassEvent)
    assert event.receiver_id == "HCY-10"


def test_parses_an_incomplete_pass_without_a_receiver() -> None:
    event = parse_match_event(pass_(outcome="incomplete", receiverId=None))

    assert isinstance(event, PassEvent)
    assert event.receiver_id is None


def test_parses_a_goal_with_the_score_after_it() -> None:
    event = parse_match_event(goal())

    assert isinstance(event, GoalEvent)
    assert (event.score_after.home, event.score_after.away) == (2, 0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("eventId", "m41-e0187"),  # belongs to another match
        ("eventId", "e0187"),
        ("matchId", "match-42"),
        ("seq", 0),
        ("version", 0),
        ("teamId", "hcy"),
        ("playerId", "HCY-9"),
        ("playerId", "NGT-09"),  # not on the shooting team
        ("clock", {"period": 3, "minute": 67, "second": 12}),
        ("clock", {"period": 2, "minute": 67, "second": 60}),
        ("clock", {"period": 2, "minute": 30, "second": 0}),  # first-half minute in period 2
        ("clock", {"period": 1, "minute": 60, "second": 0}),  # beyond 15 minutes of added time
        ("origin", {"x": 105.5, "y": 41.2}),
        ("origin", {"x": 10.0, "y": -0.1}),
        ("speedKmh", -1.0),
        ("speedKmh", 250.0),
        ("pressure", 1.2),
        ("wallClock", "2026-10-24T15:07:12"),  # no timezone
        ("type", "DIVE"),
        ("unexpected", "field"),
    ],
)
def test_refuses_malformed_events(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        parse_match_event(shot(**{field: value}))


def test_refuses_a_completed_pass_without_a_receiver() -> None:
    with pytest.raises(ValidationError, match="receiver"):
        parse_match_event(pass_(receiverId=None))


def test_refuses_an_incomplete_pass_with_a_receiver() -> None:
    with pytest.raises(ValidationError, match="receiver"):
        parse_match_event(pass_(outcome="incomplete"))


def test_refuses_a_goal_whose_assist_is_the_scorer() -> None:
    with pytest.raises(ValidationError, match="assist"):
        parse_match_event(goal(assistId="HCY-09"))


def test_refuses_a_negative_score() -> None:
    with pytest.raises(ValidationError):
        parse_match_event(goal(scoreAfter={"home": -1, "away": 0}))
