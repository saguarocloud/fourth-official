"""The deterministic Verifier: an insight passes only if every fact in it is true at its moment.

Checks, in order: the insight is about the moment; each text (headline and claims) has no bare
numbers or names and every reference resolves in the match without reaching past the moment;
each claim's evidence exists, is not from the future, and has not been voided or superseded.
"""

from collections.abc import Iterator

from fourth_official_contracts import (
    Finding,
    FindingCode,
    Insight,
    Moment,
    Verdict,
    claim_references,
    club_of,
)
from fourth_official_verifier.facts import MatchFacts
from fourth_official_verifier.text import bare_numbers, raw_names, unverified_names

MAX_FINDINGS = 64
MAX_DETAIL = 200
MAX_EXAMPLES = 3


def _finding(claim_id: str | None, code: FindingCode, detail: str) -> Finding:
    return Finding(claim_id=claim_id, code=code, detail=detail[:MAX_DETAIL])


def _examples(items: list[str]) -> str:
    shown = ", ".join(f"'{i[:24]}'" for i in items[:MAX_EXAMPLES])
    return shown + (f" and {len(items) - MAX_EXAMPLES} more" if len(items) > MAX_EXAMPLES else "")


def _text_findings(
    claim_id: str | None, text: str, moment: Moment, facts: MatchFacts
) -> Iterator[Finding]:
    if numbers := bare_numbers(text):
        yield _finding(claim_id, "BARE_NUMBER", f"{_examples(numbers)} not rendered from evidence")
    players = list(facts.player_names.values())
    if names := raw_names(text, players):
        yield _finding(claim_id, "RAW_NAME", f"{_examples(names)} written out; use a reference")
    if unknown := unverified_names(text, names):
        yield _finding(claim_id, "UNVERIFIED_NAME", f"{_examples(unknown)} is not a known name")
    clubs = {facts.match.context.home, facts.match.context.away}
    for kind, argument in claim_references(text):
        if kind == "player" and (
            argument not in facts.player_names or club_of(argument) not in clubs
        ):
            yield _finding(claim_id, "UNKNOWN_PLAYER", f"{argument} is not in either squad")
        elif kind == "club" and argument not in clubs:
            yield _finding(claim_id, "UNKNOWN_CLUB", f"{argument} is not playing")
        elif kind == "minute" and int(argument) > moment.clock.minute:
            yield _finding(
                claim_id,
                "FUTURE_MINUTE",
                f"minute {argument} is after the moment ({moment.clock.minute}')",
            )
        elif kind == "value":
            snapshot = facts.snapshots.get(argument)
            if snapshot is not None and snapshot.value is None:
                yield _finding(claim_id, "UNDEFINED_VALUE", f"{argument} has no value to quote")


def _evidence_findings(insight: Insight, moment: Moment, facts: MatchFacts) -> Iterator[Finding]:
    events = {e.event_id: e for e in facts.match.events}
    # Explaining a VAR overturn means citing the event it ruled out.
    explained = set(moment.event_ids) if moment.kind == "var_overturn" else set()
    for claim in insight.claims:
        for event_id in claim.evidence.event_ids:
            event = events.get(event_id)
            if event is None:
                yield _finding(claim.claim_id, "EVIDENCE_NOT_FOUND", f"no event {event_id}")
            elif event.seq > insight.as_of_seq:
                yield _finding(claim.claim_id, "FUTURE_EVIDENCE", f"{event_id} is after the moment")
            elif event_id in facts.voided and event_id not in explained:
                yield _finding(claim.claim_id, "VOIDED_EVIDENCE", f"{event_id} was voided")
        for snapshot_id in claim.evidence.metric_snapshot_ids:
            snapshot = facts.snapshots.get(snapshot_id)
            if snapshot is None:
                yield _finding(claim.claim_id, "SNAPSHOT_NOT_FOUND", f"no snapshot {snapshot_id}")
            elif snapshot.as_of_seq > insight.as_of_seq:
                yield _finding(
                    claim.claim_id, "FUTURE_EVIDENCE", f"{snapshot_id} is after the moment"
                )
            elif snapshot_id in facts.superseded:
                yield _finding(
                    claim.claim_id, "SUPERSEDED_EVIDENCE", f"{snapshot_id} has been restated"
                )


def _findings(insight: Insight, moment: Moment, facts: MatchFacts) -> Iterator[Finding]:
    if (insight.moment_id, insight.as_of_seq) != (moment.moment_id, moment.as_of_seq):
        yield _finding(None, "MOMENT_MISMATCH", f"insight is not about {moment.moment_id}")
        return
    yield from _text_findings(None, insight.headline, moment, facts)
    for claim in insight.claims:
        yield from _text_findings(claim.claim_id, claim.text, moment, facts)
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
