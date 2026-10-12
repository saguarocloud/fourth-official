"""Planted lies: each true insight the pipeline published, made wrong in one deliberate way, to
measure whether the Verifier refuses what it exists to refuse (plan §9.2, "verifier catch rate").

The lies are made by code from the run itself, so every configuration faces the same kinds of lie
about its own insights: a player who took no part, a minute still to come, a bare number, an
invented name, evidence that does not exist, and evidence VAR has already ruled out.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from pydantic import ValidationError

from fourth_official_contracts import (
    Claim,
    Insight,
    InsightEntry,
    Moment,
    MomentEntry,
    Ratio,
    claim_references,
    parse_insight,
)
from fourth_official_proving.factcheck import EXPLAINS_VOIDS
from fourth_official_proving.runner import MatchRun
from fourth_official_replay import facts_for
from fourth_official_verifier import MatchFacts, verify

MUTATIONS = (
    "absent_player",
    "future_minute",
    "bare_number",
    "invented_name",
    "missing_evidence",
    "voided_evidence",
)
# Far enough ahead to be after the moment, and still a minute a match can reach.
MINUTES_AHEAD = 3
LAST_MINUTE = 130
# A name no squad holds: invented, not borrowed from anyone real.
INVENTED_NAME = "Zorvath"
# An event number past the end of any match.
MISSING_EVENT = 99_999
_PARTICIPANTS = ("player_id", "scorer_id", "assist_id", "receiver_id", "victim_id", "target_id")


@dataclass(frozen=True, slots=True)
class PlantedLie:
    mutation: str
    original: Insight
    insight: Insight
    moment: Moment


def _with_first_claim(insight: Insight, text: str, event_ids: tuple[str, ...]) -> Insight | None:
    first, *rest = insight.claims
    changed = Claim(
        claim_id=first.claim_id,
        type=first.type,
        text=text,
        evidence=first.evidence.model_copy(update={"event_ids": event_ids}),
    ).to_wire()
    wire = insight.to_wire() | {"claims": [changed, *(c.to_wire() for c in rest)]}
    try:
        return parse_insight(wire)
    except ValidationError:
        return None


def _absent_player(insight: Insight, facts: MatchFacts) -> str | None:
    first = insight.claims[0]
    cited = set(first.evidence.event_ids)
    involved = {
        value
        for event in facts.match.events
        if event.event_id in cited
        for name in _PARTICIPANTS
        if isinstance(value := getattr(event, name, None), str)
    }
    absent = sorted(p for p in facts.player_names if p not in involved)
    if not absent:
        return None
    players = [a for kind, a in claim_references(first.text) if kind == "player"]
    if players:
        return first.text.replace(f"{{{{player:{players[0]}}}}}", f"{{{{player:{absent[0]}}}}}", 1)
    return f"{{{{player:{absent[0]}}}}} and {first.text}"


def _future_minute(insight: Insight, moment: Moment) -> str | None:
    later = moment.clock.minute + MINUTES_AHEAD
    if later > LAST_MINUTE:
        return None
    first = insight.claims[0]
    minutes = [a for kind, a in claim_references(first.text) if kind == "minute"]
    if minutes:
        return first.text.replace(f"{{{{minute:{minutes[0]}}}}}", f"{{{{minute:{later}}}}}", 1)
    return f"{first.text} at {{{{minute:{later}}}}}"


def _lies(insight: Insight, moment: Moment, facts: MatchFacts) -> Iterator[tuple[str, Insight]]:
    first = insight.claims[0]
    events = first.evidence.event_ids
    # The VAR decision's own insight cites the goal it rules out: citing it again is no lie.
    cited = {e for c in insight.claims for e in c.evidence.event_ids}
    voided_before = sorted(
        e
        for e, seq in facts.voided.items()
        if seq <= insight.as_of_seq and e not in cited and moment.kind != EXPLAINS_VOIDS
    )
    candidates: dict[str, tuple[str | None, tuple[str, ...]]] = {
        "absent_player": (_absent_player(insight, facts), events),
        "future_minute": (_future_minute(insight, moment), events),
        "bare_number": (f"{first.text} 3", events),
        "invented_name": (f"{first.text} with {INVENTED_NAME}", events),
        "missing_evidence": (first.text, (*events, f"{insight.match_id}-e{MISSING_EVENT}")),
        "voided_evidence": (
            first.text if voided_before else None,
            (*events, *voided_before[:1]),
        ),
    }
    for mutation, (text, event_ids) in candidates.items():
        if text is None:
            continue
        lie = _with_first_claim(insight, text, event_ids)
        if lie is not None and lie != insight:
            yield mutation, lie


def planted_lies(run: MatchRun) -> tuple[PlantedLie, ...]:
    """Every lie that can be made from each insight the run published and the Verifier passed."""
    facts = facts_for(run.record)
    moments = {e.moment.moment_id: e.moment for e in run.entries if isinstance(e, MomentEntry)}
    lies: list[PlantedLie] = []
    for entry in run.entries:
        if not isinstance(entry, InsightEntry) or not entry.verdict.passed:
            continue
        moment = moments.get(entry.insight.moment_id)
        if moment is None:
            continue
        for mutation, lie in _lies(entry.insight, moment, facts):
            lies.append(PlantedLie(mutation, entry.insight, lie, moment))
    return tuple(lies)


def verifier_catch(runs: Iterable[MatchRun]) -> Ratio:
    """Planted lies the Verifier refused, of all planted."""
    hit = of = 0
    for run in runs:
        facts = facts_for(run.record)
        for lie in planted_lies(run):
            of += 1
            hit += not verify(lie.insight, lie.moment, facts).passed
    return Ratio(hit=hit, of=of)
