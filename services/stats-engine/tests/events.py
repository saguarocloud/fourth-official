"""Tiny builders for hand-computed fixtures: each takes only what a metric test cares about."""

from datetime import UTC, datetime, timedelta

from fourth_official_contracts import (
    CarryEvent,
    InterceptionEvent,
    MatchClock,
    PassEvent,
    PeriodEndEvent,
    PitchPoint,
    PossessionChangeEvent,
    PressureEvent,
    SetPieceEvent,
    ShotEvent,
    TackleEvent,
)

MATCH = "m42"
KICKOFF = datetime(2026, 10, 24, 14, 0, tzinfo=UTC)


def _envelope(
    seq: int, minute: int, second: int = 0, period: int | None = None
) -> dict[str, object]:
    if period is None:
        period = 1 if minute < 45 else 2
    return {
        "event_id": f"{MATCH}-e{seq:04d}",
        "match_id": MATCH,
        "seq": seq,
        "version": 1,
        "clock": MatchClock(period=period, minute=minute, second=second),  # type: ignore[arg-type]
        "wall_clock": KICKOFF + timedelta(minutes=minute, seconds=second),
    }


def pass_(
    seq: int,
    minute: int,
    team: str,
    *,
    origin: tuple[float, float] = (40.0, 34.0),
    end: tuple[float, float] = (55.0, 34.0),
    complete: bool = True,
    kind: str = "ground",
    second: int = 0,
    period: int | None = None,
) -> PassEvent:
    # Minutes from 45 default to the second half; pass period=1 for first-half added time.
    return PassEvent(
        **_envelope(seq, minute, second, period),  # type: ignore[arg-type]
        type="PASS",
        team_id=team,
        player_id=f"{team}-08",
        origin=PitchPoint(x=origin[0], y=origin[1]),
        end=PitchPoint(x=end[0], y=end[1]),
        outcome="complete" if complete else "incomplete",
        receiver_id=f"{team}-10" if complete else None,
        kind=kind,  # type: ignore[arg-type]
        speed_kmh=50.0,
    )


def carry(seq: int, minute: int, team: str) -> CarryEvent:
    return CarryEvent(
        **_envelope(seq, minute),  # type: ignore[arg-type]
        type="CARRY",
        team_id=team,
        player_id=f"{team}-07",
        origin=PitchPoint(x=40.0, y=34.0),
        end=PitchPoint(x=46.0, y=34.0),
    )


def shot(
    seq: int,
    minute: int,
    team: str,
    *,
    at: tuple[float, float] = (94.0, 34.0),
    outcome: str = "saved",
    body_part: str = "right_foot",
    pressure: float = 0.0,
    speed: float = 100.0,
    period: int | None = None,
) -> ShotEvent:
    return ShotEvent(
        **_envelope(seq, minute, period=period),  # type: ignore[arg-type]
        type="SHOT",
        team_id=team,
        player_id=f"{team}-09",
        origin=PitchPoint(x=at[0], y=at[1]),
        body_part=body_part,  # type: ignore[arg-type]
        outcome=outcome,  # type: ignore[arg-type]
        speed_kmh=speed,
        pressure=pressure,
    )


def pressure(
    seq: int,
    minute: int,
    team: str,
    opponent: str,
    *,
    at: tuple[float, float] = (50.0, 34.0),
    intensity: float = 0.5,
    second: int = 0,
) -> PressureEvent:
    return PressureEvent(
        **_envelope(seq, minute, second),  # type: ignore[arg-type]
        type="PRESSURE",
        team_id=team,
        player_id=f"{team}-07",
        at=PitchPoint(x=at[0], y=at[1]),
        target_id=f"{opponent}-08",
        intensity=intensity,
    )


def tackle(
    seq: int,
    minute: int,
    team: str,
    opponent: str,
    *,
    at: tuple[float, float] = (50.0, 34.0),
    won: bool = True,
) -> TackleEvent:
    return TackleEvent(
        **_envelope(seq, minute),  # type: ignore[arg-type]
        type="TACKLE",
        team_id=team,
        player_id=f"{team}-04",
        at=PitchPoint(x=at[0], y=at[1]),
        opponent_id=f"{opponent}-08",
        outcome="won" if won else "lost",
    )


def interception(
    seq: int, minute: int, team: str, *, at: tuple[float, float] = (50.0, 34.0)
) -> InterceptionEvent:
    return InterceptionEvent(
        **_envelope(seq, minute),  # type: ignore[arg-type]
        type="INTERCEPTION",
        team_id=team,
        player_id=f"{team}-06",
        at=PitchPoint(x=at[0], y=at[1]),
    )


def turnover(seq: int, minute: int, gaining_team: str) -> PossessionChangeEvent:
    return PossessionChangeEvent(
        **_envelope(seq, minute),  # type: ignore[arg-type]
        type="POSSESSION_CHANGE",
        team_id=gaining_team,
        cause="interception",
    )


def period_end(seq: int, minute: int, *, second: int = 0) -> PeriodEndEvent:
    """End of the first half (minutes 45-59 are first-half added time here)."""
    return PeriodEndEvent(**_envelope(seq, minute, second, period=1), type="PERIOD_END")  # type: ignore[arg-type]


def penalty_awarded(
    seq: int, minute: int, team: str, *, at: tuple[float, float] = (94.0, 34.0)
) -> SetPieceEvent:
    return SetPieceEvent(
        **_envelope(seq, minute),  # type: ignore[arg-type]
        type="SET_PIECE",
        team_id=team,
        player_id=f"{team}-09",
        kind="penalty",
        at=PitchPoint(x=at[0], y=at[1]),
    )
