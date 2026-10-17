"""The matchday wall: each match as the Control Room shows it, computed from its feed."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import MatchdayWall, parse_matchday_wall

CLOCK = {"period": 2, "minute": 68, "second": 41}


def match(**overrides: object) -> dict[str, Any]:
    return {
        "matchId": "m42",
        "home": "HCY",
        "away": "NGT",
        "state": "running",
        "score": {"home": 1, "away": 0},
        "clock": CLOCK,
        "items": 12,
        "pendingApprovals": 2,
        "corrections": 1,
        "onAir": ["northlight-sport"],
        **overrides,
    }


def activity(**overrides: object) -> dict[str, Any]:
    return {
        "entrySeq": 140,
        "matchId": "m42",
        "tenantId": "tribuna-austral",
        "state": "pending_approval",
        "headline": "Northgate's press fades after the hour",
        "clock": CLOCK,
        "aiWritten": True,
        **overrides,
    }


def correction(**overrides: object) -> dict[str, Any]:
    return {
        "matchId": "m42",
        "correctionId": "c-m42-0001",
        "summary": "Harbour City goal at 67' ruled out for offside",
        "outText": "2-0",
        "inText": "1-0",
        "eventClock": {"period": 2, "minute": 67, "second": 12},
        "receivedClock": {"period": 2, "minute": 68, "second": 3},
        "itemsCorrected": 6,
        "partners": 3,
        "languages": 3,
        "elapsedMs": 40,
        **overrides,
    }


def wall(**overrides: object) -> dict[str, Any]:
    return {
        "generatedAt": "2026-10-16T21:00:00Z",
        "matches": [match()],
        "activity": [activity()],
        "latestCorrection": correction(),
        **overrides,
    }


def test_a_wall_round_trips_on_the_wire() -> None:
    parsed = parse_matchday_wall(wall())

    assert isinstance(parsed, MatchdayWall)
    assert parse_matchday_wall(parsed.to_wire()) == parsed


def test_a_match_not_started_has_no_clock_and_nothing_on_air() -> None:
    parse_matchday_wall(
        wall(
            matches=[
                match(
                    state="idle", clock=None, onAir=[], items=0, pendingApprovals=0, corrections=0
                )
            ]
        )
    )
    with pytest.raises(ValidationError, match="not started"):
        parse_matchday_wall(wall(matches=[match(state="idle", clock=None)]))


def test_a_partner_is_on_air_once_and_held_items_are_items() -> None:
    with pytest.raises(ValidationError, match="once"):
        parse_matchday_wall(wall(matches=[match(onAir=["northlight-sport", "northlight-sport"])]))
    with pytest.raises(ValidationError, match="items"):
        parse_matchday_wall(wall(matches=[match(items=1, pendingApprovals=2)]))


def test_activity_is_newest_first_and_about_the_wall_s_matches() -> None:
    older = activity(entrySeq=100)
    with pytest.raises(ValidationError, match="newest"):
        parse_matchday_wall(wall(activity=[older, activity()]))
    with pytest.raises(ValidationError, match="match"):
        parse_matchday_wall(wall(activity=[activity(matchId="m99")]))


def test_a_correction_cannot_reach_more_partners_or_languages_than_there_are() -> None:
    with pytest.raises(ValidationError):
        parse_matchday_wall(wall(latestCorrection=correction(partners=4)))
    parse_matchday_wall(wall(latestCorrection=None))
