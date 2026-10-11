"""Builders for the events that make moments, on top of the stats engine's metric builders."""

from datetime import UTC, datetime, timedelta

from fourth_official_contracts import (
    CardEvent,
    FoulEvent,
    GoalEvent,
    MatchClock,
    PitchPoint,
    Score,
    VarCheckEvent,
    VarDecisionEvent,
)

MATCH = "m42"
KICKOFF = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)


def envelope(seq: int, minute: int, second: int = 0) -> dict[str, object]:
    period = 1 if minute < 45 else 2
    return {
        "event_id": f"{MATCH}-e{seq:04d}",
        "match_id": MATCH,
        "seq": seq,
        "version": 1,
        "clock": MatchClock(period=period, minute=minute, second=second),  # type: ignore[arg-type]
        "wall_clock": KICKOFF + timedelta(minutes=minute, seconds=second),
    }


def goal(seq: int, minute: int, team: str, *, shot_seq: int, home: int, away: int) -> GoalEvent:
    return GoalEvent(
        **envelope(seq, minute),  # type: ignore[arg-type]
        type="GOAL",
        team_id=team,
        scorer_id=f"{team}-09",
        assist_id=None,
        own_goal=False,
        shot_event_id=f"{MATCH}-e{shot_seq:04d}",
        score_after=Score(home=home, away=away),
    )


def foul(seq: int, minute: int, team: str, victim_team: str) -> FoulEvent:
    return FoulEvent(
        **envelope(seq, minute),  # type: ignore[arg-type]
        type="FOUL",
        team_id=team,
        player_id=f"{team}-04",
        at=PitchPoint(x=50.0, y=30.0),
        victim_id=f"{victim_team}-10",
    )


def card(seq: int, minute: int, team: str, *, kind: str, foul_seq: int | None) -> CardEvent:
    return CardEvent(
        **envelope(seq, minute),  # type: ignore[arg-type]
        type="CARD",
        team_id=team,
        player_id=f"{team}-04",
        card=kind,  # type: ignore[arg-type]
        foul_event_id=f"{MATCH}-e{foul_seq:04d}" if foul_seq else None,
    )


def var_check(seq: int, minute: int, *, target_seq: int) -> VarCheckEvent:
    return VarCheckEvent(
        **envelope(seq, minute, 20),  # type: ignore[arg-type]
        type="VAR_CHECK",
        target_event_id=f"{MATCH}-e{target_seq:04d}",
        reason="goal",
    )


def var_decision(seq: int, minute: int, *, target_seq: int, overturned: bool) -> VarDecisionEvent:
    return VarDecisionEvent(
        **envelope(seq, minute, 50),  # type: ignore[arg-type]
        type="VAR_DECISION",
        target_event_id=f"{MATCH}-e{target_seq:04d}",
        decision="overturned" if overturned else "confirmed",
        reason="offside" if overturned else "none",
    )
