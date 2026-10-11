"""One valid example of every event type, plus the cross-player rules each type enforces."""

from typing import Any

import pytest
from pydantic import ValidationError

from builders import envelope, goal, pass_
from fourth_official_contracts import parse_match_event

AT = {"x": 52.5, "y": 34.0}

VALID: dict[str, dict[str, Any]] = {
    "CARRY": {"teamId": "HCY", "playerId": "HCY-08", "origin": AT, "end": {"x": 60.0, "y": 30.0}},
    "SAVE": {"teamId": "NGT", "playerId": "NGT-01", "shotEventId": "m42-e0186"},
    "TACKLE": {
        "teamId": "NGT",
        "playerId": "NGT-04",
        "at": AT,
        "opponentId": "HCY-08",
        "outcome": "won",
    },
    "INTERCEPTION": {"teamId": "NGT", "playerId": "NGT-06", "at": AT},
    "CLEARANCE": {"teamId": "NGT", "playerId": "NGT-05", "at": AT},
    "PRESSURE": {
        "teamId": "NGT",
        "playerId": "NGT-08",
        "at": AT,
        "targetId": "HCY-08",
        "intensity": 0.7,
    },
    "FOUL": {"teamId": "NGT", "playerId": "NGT-04", "at": AT, "victimId": "HCY-09"},
    "CARD": {"teamId": "NGT", "playerId": "NGT-04", "card": "yellow", "foulEventId": "m42-e0190"},
    "OFFSIDE": {"teamId": "HCY", "playerId": "HCY-09", "at": AT},
    "SET_PIECE": {
        "teamId": "HCY",
        "playerId": "HCY-07",
        "kind": "corner",
        "at": {"x": 105.0, "y": 0.0},
    },
    "SUBSTITUTION": {"teamId": "HCY", "playerOffId": "HCY-09", "playerOnId": "HCY-19"},
    "POSSESSION_CHANGE": {"teamId": "NGT", "cause": "interception"},
    "VAR_CHECK": {"targetEventId": "m42-e0188", "reason": "goal"},
    "VAR_DECISION": {"targetEventId": "m42-e0188", "decision": "overturned", "reason": "offside"},
    "PERIOD_START": {},
    "PERIOD_END": {},
}


@pytest.mark.parametrize(("event_type", "fields"), sorted(VALID.items()))
def test_every_event_type_parses_and_round_trips(event_type: str, fields: dict[str, Any]) -> None:
    raw = envelope(type=event_type, **fields)

    event = parse_match_event(raw)

    assert event.type == event_type
    assert event.to_wire() == raw


@pytest.mark.parametrize(
    ("event_type", "overrides"),
    [
        ("TACKLE", {"opponentId": "NGT-08"}),
        ("PRESSURE", {"targetId": "NGT-09"}),
        ("FOUL", {"victimId": "NGT-09"}),
        ("SUBSTITUTION", {"playerOnId": "NGT-19"}),
        ("SUBSTITUTION", {"playerOnId": "HCY-09"}),
    ],
)
def test_refuses_impossible_player_relationships(
    event_type: str, overrides: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        parse_match_event(envelope(type=event_type, **{**VALID[event_type], **overrides}))


def test_refuses_a_pass_received_by_the_passer() -> None:
    with pytest.raises(ValidationError, match="receiver"):
        parse_match_event(pass_(receiverId="HCY-08"))


def test_refuses_a_pass_received_by_an_opponent() -> None:
    with pytest.raises(ValidationError, match="receiver"):
        parse_match_event(pass_(receiverId="NGT-10"))


def test_accepts_an_own_goal_credited_to_the_opponent() -> None:
    event = parse_match_event(goal(scorerId="NGT-05", assistId=None, ownGoal=True))

    assert event.type == "GOAL"


@pytest.mark.parametrize(
    "overrides",
    [
        {"scorerId": "NGT-05", "ownGoal": False},  # scorer plays for the other side
        {"ownGoal": True},  # an own goal by the credited team's own player
        {"scorerId": "NGT-05", "assistId": "HCY-10", "ownGoal": True},  # own goals have no assist
        {"assistId": "NGT-10"},  # assist from the other side
    ],
)
def test_refuses_inconsistent_goal_credit(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        parse_match_event(goal(**overrides))
