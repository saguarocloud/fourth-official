"""The deterministic Verifier: an insight passes only if every fact in it is true at its moment.

Checks, in order: the insight is about the moment; each text (headline and claims) uses only
allowed characters and words, states no number or name itself and nothing about the future;
every reference resolves, and every player and minute it names appears in the cited events;
the cited evidence exists, is not from after the moment, and had not been voided or restated by
then. Finding details never repeat the claim text beyond single ASCII words.
"""

import re
from collections.abc import Iterable, Iterator

from fourth_official_contracts import (
    MAX_FINDINGS,
    CardEvent,
    Finding,
    FindingCode,
    Insight,
    MatchEvent,
    Moment,
    Verdict,
    claim_references,
    club_of,
)
from fourth_official_verifier.facts import MatchFacts
from fourth_official_verifier.text import SECOND_YELLOW, TextProblems, check_text

MAX_DETAIL = 200
MAX_EXAMPLES = 3
MAX_EXAMPLE_LENGTH = 12
_PARTICIPANTS = (
    "player_id",
    "scorer_id",
    "assist_id",
    "receiver_id",
    "victim_id",
    "target_id",
    "opponent_id",
    "player_off_id",
    "player_on_id",
)


def _finding(claim_id: str | None, code: FindingCode, detail: str) -> Finding:
    return Finding(claim_id=claim_id, code=code, detail=detail[:MAX_DETAIL])


def _examples(items: list[str]) -> str:
    shown = ", ".join(f"'{i[:MAX_EXAMPLE_LENGTH]}'" for i in items[:MAX_EXAMPLES])
    more = len(items) - MAX_EXAMPLES
    return shown + (f" and {more} more" if more > 0 else "")


def _word_findings(claim_id: str | None, problems: TextProblems) -> Iterator[Finding]:
    if problems.unsupported:
        yield _finding(claim_id, "UNSUPPORTED_CHARACTER", "use plain ASCII text outside references")
        return
    checks: list[tuple[list[str], FindingCode, str]] = [
        (problems.numbers, "BARE_NUMBER", "numbers must be references"),
        (problems.raw_names, "RAW_NAME", "names must be references"),
        (problems.names, "UNVERIFIED_NAME", "capitalised words that are not known terms"),
        (problems.unknown_words, "UNKNOWN_WORD", "words outside the claim vocabulary"),
        (problems.future, "FUTURE_WORDING", "wording about what happens later"),
    ]
    for found, code, why in checks:
        if found:
            yield _finding(claim_id, code, f"{why}: {_examples(found)}")


def _evidenced(text: str, events: Iterable[MatchEvent]) -> list[re.Pattern[str]]:
    """Count phrases the cited events state: a second yellow, for the player the text names (if
    it names one)."""
    named = {argument for kind, argument in claim_references(text) if kind == "player"}
    cards = [e for e in events if isinstance(e, CardEvent) and e.card == "second_yellow"]
    if any(not named or card.player_id in named for card in cards):
        return [SECOND_YELLOW]
    return []


def _participants(events: Iterable[MatchEvent]) -> set[str]:
    return {
        value
        for event in events
        for name in _PARTICIPANTS
        if isinstance(value := getattr(event, name, None), str)
    }


def _reference_findings(  # noqa: PLR0917 - one claim's text and its context
    claim_id: str | None,
    text: str,
    cited: list[MatchEvent],
    moment: Moment,
    facts: MatchFacts,
) -> Iterator[Finding]:
    clubs = {facts.match.context.home, facts.match.context.away}
    involved = _participants(cited)
    minutes = {e.clock.minute for e in cited}
    for kind, argument in claim_references(text):
        if kind == "player":
            if argument not in facts.player_names or club_of(argument) not in clubs:
                yield _finding(claim_id, "UNKNOWN_PLAYER", f"{argument} is not in either squad")
            elif argument not in involved:
                yield _finding(
                    claim_id, "PLAYER_NOT_IN_EVIDENCE", f"{argument} is in no cited event"
                )
        elif kind == "club" and argument not in clubs:
            yield _finding(claim_id, "UNKNOWN_CLUB", f"{argument} is not playing")
        elif kind == "minute":
            if int(argument) > moment.clock.minute:
                yield _finding(claim_id, "FUTURE_MINUTE", f"minute {argument} is after the moment")
            elif int(argument) not in minutes:
                yield _finding(
                    claim_id, "MINUTE_NOT_IN_EVIDENCE", f"minute {argument} is in no cited event"
                )
        elif kind == "value":
            snapshot = facts.snapshots.get(argument)
            if snapshot is not None and snapshot.value is None:
                yield _finding(claim_id, "UNDEFINED_VALUE", f"{argument} has no value to quote")


def _evidence_findings(insight: Insight, moment: Moment, facts: MatchFacts) -> Iterator[Finding]:
    events = {e.event_id: e for e in facts.match.events}
    # Explaining a VAR overturn means citing the event it ruled out.
    explained = set(moment.event_ids) if moment.kind == "var_overturn" else set()
    seq = insight.as_of_seq
    for claim in insight.claims:
        for event_id in claim.evidence.event_ids:
            event = events.get(event_id)
            if event is None:
                yield _finding(claim.claim_id, "EVIDENCE_NOT_FOUND", f"no event {event_id}")
            elif event.seq > seq:
                yield _finding(claim.claim_id, "FUTURE_EVIDENCE", f"{event_id} is after the moment")
            elif facts.voided_by(event_id, seq) and event_id not in explained:
                yield _finding(claim.claim_id, "VOIDED_EVIDENCE", f"{event_id} was voided")
        for snapshot_id in claim.evidence.metric_snapshot_ids:
            snapshot = facts.snapshots.get(snapshot_id)
            if snapshot is None:
                yield _finding(claim.claim_id, "SNAPSHOT_NOT_FOUND", f"no snapshot {snapshot_id}")
            elif snapshot.as_of_seq > seq:
                yield _finding(
                    claim.claim_id, "FUTURE_EVIDENCE", f"{snapshot_id} is after the moment"
                )
            elif facts.superseded_by(snapshot_id, seq):
                yield _finding(
                    claim.claim_id, "SUPERSEDED_EVIDENCE", f"{snapshot_id} has been restated"
                )


def _findings(insight: Insight, moment: Moment, facts: MatchFacts) -> Iterator[Finding]:
    if (insight.moment_id, insight.as_of_seq) != (moment.moment_id, moment.as_of_seq):
        yield _finding(None, "MOMENT_MISMATCH", f"insight is not about {moment.moment_id}")
        return
    events = {e.event_id: e for e in facts.match.events if e.seq <= insight.as_of_seq}
    players = list(facts.player_names.values())

    def cited(event_ids: Iterable[str]) -> list[MatchEvent]:
        return [events[e] for e in event_ids if e in events]

    every = cited(e for c in insight.claims for e in c.evidence.event_ids)
    yield from _word_findings(
        None, check_text(insight.headline, players, evidenced=_evidenced(insight.headline, every))
    )
    yield from _reference_findings(None, insight.headline, every, moment, facts)
    for claim in insight.claims:
        own = cited(claim.evidence.event_ids)
        yield from _word_findings(
            claim.claim_id, check_text(claim.text, players, evidenced=_evidenced(claim.text, own))
        )
        yield from _reference_findings(claim.claim_id, claim.text, own, moment, facts)
    yield from _evidence_findings(insight, moment, facts)


def verify(insight: Insight, moment: Moment, facts: MatchFacts) -> Verdict:
    """Check every fact in the insight against the match as it stood at the moment."""
    findings: list[Finding] = []
    for finding in _findings(insight, moment, facts):
        findings.append(finding)
        if len(findings) == MAX_FINDINGS:
            break
    return Verdict(
        insight_id=insight.insight_id,
        match_id=insight.match_id,
        passed=not findings,
        findings=tuple(findings),
    )
