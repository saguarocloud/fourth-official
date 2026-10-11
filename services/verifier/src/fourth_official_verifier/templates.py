"""Template insights: the deterministic last resort when no model insight passes verification.

Each moment kind has one plain template built only from references, so it passes the Verifier by
construction. Templates avoid number words ("ten men", "five minutes"): numbers are references.
"""

from fourth_official_contracts import (
    CardEvent,
    Claim,
    ClaimType,
    Evidence,
    GoalEvent,
    Insight,
    MatchEvent,
    Moment,
    Provenance,
    ShotEvent,
    VarDecisionEvent,
    insight_id_for,
)
from fourth_official_verifier.facts import MatchFacts

TEMPLATE_PROVENANCE = Provenance(
    agent="template", prompt_version="v1.0", model="none", produced_by="template"
)
_REASON_WORDS = {"offside": "offside", "foul": "a foul", "handball": "handball", "none": "a review"}

Line = tuple[ClaimType, str]


def _event[E: MatchEvent](facts: MatchFacts, event_id: str, kind: type[E]) -> E:
    event = next((e for e in facts.match.events if e.event_id == event_id), None)
    if not isinstance(event, kind):
        raise ValueError(f"{event_id} is not a {kind.__name__}")
    return event


def _goal(moment: Moment, facts: MatchFacts) -> tuple[str, list[Line]]:
    goal = _event(facts, moment.event_ids[-1], GoalEvent)
    lines: list[Line] = [
        (
            "stat",
            f"{{{{player:{goal.scorer_id}}}}} scores for {{{{club:{goal.team_id}}}}} in the "
            f"{{{{minute:{goal.clock.minute}}}}}: {{{{score}}}}.",
        )
    ]
    if goal.assist_id:
        lines.append(("stat", f"{{{{player:{goal.assist_id}}}}} provides the assist."))
    return f"{{{{club:{goal.team_id}}}}} score", lines


def _big_chance(moment: Moment, facts: MatchFacts) -> tuple[str, list[Line]]:
    shot = _event(facts, moment.event_ids[-1], ShotEvent)
    what = "misses a penalty" if len(moment.event_ids) > 1 else "goes close"
    return f"{{{{club:{shot.team_id}}}}} go close", [
        (
            "stat",
            f"{{{{player:{shot.player_id}}}}} {what} for {{{{club:{shot.team_id}}}}} in the "
            f"{{{{minute:{shot.clock.minute}}}}}.",
        )
    ]


def _red_card(moment: Moment, facts: MatchFacts) -> tuple[str, list[Line]]:
    card = _event(facts, moment.event_ids[-1], CardEvent)
    club, minute = f"{{{{club:{card.team_id}}}}}", f"{{{{minute:{card.clock.minute}}}}}"
    return f"{club} down a player", [
        (
            "stat",
            f"{{{{player:{card.player_id}}}}} is sent off in the {minute}, leaving {club} a "
            "player short.",
        )
    ]


def _var_overturn(moment: Moment, facts: MatchFacts) -> tuple[str, list[Line]]:
    decision = _event(facts, moment.event_ids[-1], VarDecisionEvent)
    target = _event(facts, moment.event_ids[0], GoalEvent)
    reason = _REASON_WORDS[decision.reason]
    return f"VAR rules out a {{{{club:{moment.club}}}}} goal", [
        (
            "milestone",
            f"VAR rules out the {{{{club:{moment.club}}}}} goal from the "
            f"{{{{minute:{target.clock.minute}}}}} for {reason}.",
        )
    ]


def _shift(moment: Moment, facts: MatchFacts) -> tuple[str, list[Line]]:
    shift = moment.shifts[0]
    club = f"{{{{club:{moment.club}}}}}"
    after, before = (
        f"{{{{value:{shift.after_snapshot_id}}}}}",
        f"{{{{value:{shift.before_snapshot_id}}}}}",
    )
    if moment.kind == "pressing_collapse":
        return f"{club} ease off the press", [
            (
                "comparison",
                f"{club} now press {after} times per opponent touch, down from {before}.",
            )
        ]
    if moment.kind == "pressing_surge":
        return f"{club} step up the press", [
            ("comparison", f"{club} now press {after} times per opponent touch, up from {before}.")
        ]
    return f"{club} change their game", [
        (
            "comparison",
            f"The {shift.metric.replace('_', ' ')} for {club} is now {after}, from {before}.",
        )
    ]


_TEMPLATES = {
    "goal": _goal,
    "big_chance": _big_chance,
    "red_card": _red_card,
    "var_overturn": _var_overturn,
}


def template_insight(moment: Moment, facts: MatchFacts, *, attempt: int = 1) -> Insight:
    """A plain, verifiable insight for the moment, from its own evidence."""
    headline, lines = _TEMPLATES.get(moment.kind, _shift)(moment, facts)
    evidence = Evidence(event_ids=moment.event_ids, metric_snapshot_ids=moment.metric_snapshot_ids)
    return Insight(
        insight_id=insight_id_for(moment.moment_id, attempt=attempt),
        match_id=moment.match_id,
        moment_id=moment.moment_id,
        as_of_seq=moment.as_of_seq,
        locale="en",
        headline=headline,
        claims=tuple(
            Claim(claim_id=f"cl-{n}", type=kind, text=text, evidence=evidence)
            for n, (kind, text) in enumerate(lines, start=1)
        ),
        provenance=TEMPLATE_PROVENANCE,
    )
