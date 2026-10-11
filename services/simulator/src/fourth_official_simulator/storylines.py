"""Storylines: scripted football that the pipeline must later notice, explain and correct.

A storyline is a list of directives laid over an otherwise ordinary simulated match: a press that
collapses at a given minute, a goal that happens on cue, a goal VAR rules out after it has been
published, a scorer the accreditation panel reassigns after the final whistle. Each directive
leaves both its football in the event stream and a ground-truth record of what really happened.
"""

import itertools
import re
from dataclasses import dataclass, fields
from typing import Literal

from fourth_official_simulator.style import TeamStyle

VarReason = Literal["VAR_OFFSIDE", "VAR_FOUL", "VAR_HANDBALL"]
# Scripted moments happen in normal time, away from the half-time boundary.
FIRST_MINUTE, LAST_MINUTE, HALF_TIME_MINUTE = 1, 89, 45
# Scripted moments need room for their own football (a goal is followed by a kick-off).
MIN_MINUTES_APART = 3
# Natural reds come on top; more than two scripted ones per side would empty the pitch.
MAX_SCRIPTED_REDS = 2
# A VAR review takes up to about ninety seconds and must end before half-time.
LAST_FIRST_HALF_VAR_MINUTE = 42
MAX_TEXT = 120
CLUB_CODE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class ScriptedGoal:
    """`club` scores in `minute`, from a completed pass into the box."""

    club: str
    minute: int


@dataclass(frozen=True, slots=True)
class RedCard:
    """A player of `club` is sent off for a foul in `minute`."""

    club: str
    minute: int


@dataclass(frozen=True, slots=True)
class StyleShift:
    """From `minute`, `club` plays with some style dials changed (unset dials stay as they are)."""

    club: str
    minute: int
    label: str
    pressing: float | None = None
    directness: float | None = None
    width: float | None = None
    tempo: float | None = None

    def __post_init__(self) -> None:
        if not self.changes:
            raise ValueError("a style shift must change at least one dial")
        TeamStyle(**dict.fromkeys(_DIALS, 0.5)).with_changes(**self.changes)  # range check

    @property
    def changes(self) -> dict[str, float]:
        return {name: value for name in _DIALS if (value := getattr(self, name)) is not None}


_DIALS = tuple(f.name for f in fields(TeamStyle))


@dataclass(frozen=True, slots=True)
class VarVoid:
    """VAR reviews `club`'s scripted goal in `goal_minute` and rules it out."""

    club: str
    goal_minute: int
    reason: VarReason = "VAR_OFFSIDE"


@dataclass(frozen=True, slots=True)
class ScorerReassigned:
    """After the final whistle, the accreditation panel credits `club`'s scripted goal in
    `goal_minute` to a different player."""

    club: str
    goal_minute: int


Directive = ScriptedGoal | RedCard | StyleShift | VarVoid | ScorerReassigned
Moment = ScriptedGoal | RedCard


@dataclass(frozen=True, slots=True)
class Storyline:
    name: str
    directives: tuple[Directive, ...]
    # Whether goals other than the scripted ones may happen.
    natural_goals: bool = True

    def __post_init__(self) -> None:
        _check_text(self.name, "storyline name")
        for directive in self.directives:
            _check_directive(directive)
        self._check_moments()
        self._check_targets()

    def _check_moments(self) -> None:
        moments = sorted(self.moments, key=lambda m: m.minute)
        for before, after in itertools.pairwise(moments):
            if after.minute - before.minute < MIN_MINUTES_APART:
                raise ValueError(
                    f"scripted moments at {before.minute}' and {after.minute}' are too close"
                )
        for club in self.clubs():
            reds = sum(1 for d in self.directives if isinstance(d, RedCard) and d.club == club)
            if reds > MAX_SCRIPTED_REDS:
                raise ValueError(f"{club} can be shown at most {MAX_SCRIPTED_REDS} scripted reds")

    def _check_targets(self) -> None:
        goals = {(g.club, g.minute) for g in self.goals}
        voided = [(v.club, v.goal_minute) for v in self.voids]
        reassigned = [(r.club, r.goal_minute) for r in self.reassignments]
        for target in [*voided, *reassigned]:
            if target not in goals:
                raise ValueError(f"no scripted goal for {target[0]} in minute {target[1]}")
        if len(set(voided)) != len(voided) or len(set(reassigned)) != len(reassigned):
            raise ValueError("a goal can be ruled out, or have its scorer reassigned, only once")
        if set(voided) & set(reassigned):
            raise ValueError("a goal ruled out by VAR cannot have its scorer reassigned")
        for _, minute in voided:
            if period_of(minute) == 1 and minute > LAST_FIRST_HALF_VAR_MINUTE:
                raise ValueError(
                    f"VAR needs about two minutes: a goal in {minute}' would be decided after "
                    "half-time"
                )

    def clubs(self) -> frozenset[str]:
        return frozenset(d.club for d in self.directives)

    @property
    def goals(self) -> tuple[ScriptedGoal, ...]:
        return tuple(d for d in self.directives if isinstance(d, ScriptedGoal))

    @property
    def moments(self) -> tuple[Moment, ...]:
        return tuple(d for d in self.directives if isinstance(d, ScriptedGoal | RedCard))

    @property
    def shifts(self) -> tuple[StyleShift, ...]:
        return tuple(d for d in self.directives if isinstance(d, StyleShift))

    @property
    def voids(self) -> tuple[VarVoid, ...]:
        return tuple(d for d in self.directives if isinstance(d, VarVoid))

    @property
    def reassignments(self) -> tuple[ScorerReassigned, ...]:
        return tuple(d for d in self.directives if isinstance(d, ScorerReassigned))

    def void_for(self, goal: ScriptedGoal) -> VarVoid | None:
        return next(
            (v for v in self.voids if (v.club, v.goal_minute) == (goal.club, goal.minute)), None
        )

    def style_at(self, club: str, base: TeamStyle, minute: int) -> TeamStyle:
        """The club's style in `minute`: the base style with every shift so far applied."""
        style = base
        for shift in sorted(self.shifts, key=lambda s: s.minute):
            if shift.club == club and shift.minute <= minute:
                style = style.with_changes(**shift.changes)
        return style


def period_of(minute: int) -> Literal[1, 2]:
    return 1 if minute < HALF_TIME_MINUTE else 2


def _check_minute(minute: object) -> None:
    if type(minute) is not int:
        raise ValueError(f"scripted minutes are a whole minute, got {minute!r}")
    if not FIRST_MINUTE <= minute <= LAST_MINUTE or minute == HALF_TIME_MINUTE:
        raise ValueError(
            f"scripted minutes run {FIRST_MINUTE}-{LAST_MINUTE}, not {HALF_TIME_MINUTE}; "
            f"got {minute}"
        )


def _check_text(text: str, what: str) -> None:
    if not 0 < len(text) <= MAX_TEXT or not text.isprintable():
        raise ValueError(f"a {what} is 1-{MAX_TEXT} printable characters on one line")


def _check_directive(directive: Directive) -> None:
    if not CLUB_CODE.match(directive.club):
        raise ValueError(f"{directive.club!r} is not a club code")
    if isinstance(directive, VarVoid | ScorerReassigned):
        _check_minute(directive.goal_minute)
    else:
        _check_minute(directive.minute)
    if isinstance(directive, StyleShift):
        _check_text(directive.label, "style shift label")
