"""Builders for raw wire-format events, so each test states only what it is about."""

WALL = "2026-10-24T15:07:12.400Z"


def envelope(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "eventId": "m42-e0187",
        "matchId": "m42",
        "seq": 187,
        "version": 1,
        "clock": {"period": 2, "minute": 67, "second": 12},
        "wallClock": WALL,
    }
    return {**base, **overrides}


def shot(**overrides: object) -> dict[str, object]:
    return (
        envelope(
            type="SHOT",
            teamId="HCY",
            playerId="HCY-09",
            origin={"x": 88.4, "y": 41.2},
            bodyPart="right_foot",
            outcome="goal",
            speedKmh=104.2,
            pressure=0.35,
        )
        | overrides
    )


def pass_(**overrides: object) -> dict[str, object]:
    return (
        envelope(
            eventId="m42-e0150",
            seq=150,
            type="PASS",
            teamId="HCY",
            playerId="HCY-08",
            origin={"x": 40.0, "y": 30.0},
            end={"x": 62.5, "y": 20.0},
            outcome="complete",
            receiverId="HCY-10",
            kind="ground",
            speedKmh=48.0,
        )
        | overrides
    )


def goal(**overrides: object) -> dict[str, object]:
    return (
        envelope(
            eventId="m42-e0188",
            seq=188,
            type="GOAL",
            teamId="HCY",
            scorerId="HCY-09",
            assistId="HCY-10",
            ownGoal=False,
            shotEventId="m42-e0187",
            scoreAfter={"home": 2, "away": 0},
        )
        | overrides
    )
