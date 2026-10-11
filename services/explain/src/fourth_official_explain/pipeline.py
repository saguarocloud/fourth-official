"""Explain a moment: draft with a model, verify, retry with the findings as feedback, try the next
model, and fall back to the deterministic template. Every attempt is recorded for provenance.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import ValidationError

from fourth_official_contracts import (
    Finding,
    Insight,
    MatchEvent,
    Moment,
    Provenance,
    Verdict,
    insight_id_for,
)
from fourth_official_explain.drafts import InsightDraft, to_insight
from fourth_official_verifier import MatchFacts, template_insight, verify

RETRIES = 2
TIMEOUT_SECONDS = 20.0
Outcome = Literal["passed", "failed", "error"]


# Events before the moment included in the briefing, besides the moment's own evidence.
LEAD_UP_EVENTS = 8


@dataclass(frozen=True, slots=True)
class Briefing:
    """What the Analyst is told up front, so most moments need no tool call: the moment's own
    evidence, the play leading up to it, and the score as it stood."""

    evidence: tuple[MatchEvent, ...]
    lead_up: tuple[MatchEvent, ...]
    score: tuple[int, int]


@dataclass(frozen=True, slots=True)
class DraftRequest:
    moment: Moment
    attempt: int
    # What the Verifier found wrong with the previous draft, if any.
    feedback: tuple[Finding, ...] = ()
    briefing: Briefing | None = None


def brief(moment: Moment, facts: MatchFacts) -> Briefing:
    published = [e for e in facts.match.events if e.seq <= moment.as_of_seq]
    cited = set(moment.event_ids)
    return Briefing(
        evidence=tuple(e for e in published if e.event_id in cited),
        lead_up=tuple(e for e in published if e.event_id not in cited)[-LEAD_UP_EVENTS:],
        score=facts.score_at(moment.as_of_seq),
    )


class Drafter(Protocol):
    """A model that drafts insights, and the provenance it signs them with."""

    @property
    def provenance(self) -> Provenance: ...

    async def draft(self, request: DraftRequest) -> InsightDraft: ...


@dataclass(frozen=True, slots=True)
class Attempt:
    number: int
    agent: str
    model: str
    outcome: Outcome
    findings: tuple[str, ...] = ()
    # The kind of failure when the model itself failed (a timeout, a service error).
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Explanation:
    moment: Moment
    # None only if even the template failed verification (which a test rules out).
    insight: Insight | None
    verdict: Verdict
    attempts: tuple[Attempt, ...]


def _malformed(moment: Moment, attempt: int, error: ValidationError) -> Verdict:
    # Where and why, from the contract's own messages; never the draft's text itself.
    problems = []
    for problem in error.errors(include_input=False):
        where = ".".join(str(part) for part in problem["loc"]) or "insight"
        problems.append(f"{where}: {problem['msg'].removeprefix('Value error, ')}")
    detail = "the draft breaks the insight contract: " + "; ".join(problems[:3])
    return Verdict(
        insight_id=insight_id_for(moment.moment_id, attempt=attempt),
        match_id=moment.match_id,
        passed=False,
        findings=(Finding(claim_id=None, code="MALFORMED_INSIGHT", detail=detail[:200]),),
    )


def _check(
    draft: InsightDraft, moment: Moment, facts: MatchFacts, *, attempt: int, provenance: Provenance
) -> tuple[Insight | None, Verdict]:
    try:
        insight = to_insight(draft, moment, attempt=attempt, provenance=provenance)
    except ValidationError as broken:
        return None, _malformed(moment, attempt, broken)
    return insight, verify(insight, moment, facts)


async def explain(
    moment: Moment,
    facts: MatchFacts,
    drafters: Sequence[Drafter],
    *,
    retries: int = RETRIES,
    timeout: float = TIMEOUT_SECONDS,
) -> Explanation:
    """The best verified insight for the moment, and the record of how it was reached."""
    attempts: list[Attempt] = []
    briefing = brief(moment, facts)
    for drafter in drafters:
        provenance = drafter.provenance
        feedback: tuple[Finding, ...] = ()
        for _ in range(1 + retries):
            number = len(attempts) + 1
            request = DraftRequest(moment, number, feedback, briefing)
            try:
                # A timeout in the same task: MCP sessions must close in the task that opened them.
                async with asyncio.timeout(timeout):
                    draft = await drafter.draft(request)
            except Exception as failure:
                attempts.append(
                    Attempt(
                        number,
                        provenance.agent,
                        provenance.model,
                        "error",
                        error=type(failure).__name__,
                    )
                )
                break
            insight, verdict = _check(draft, moment, facts, attempt=number, provenance=provenance)
            codes = tuple(f.code for f in verdict.findings)
            if insight is not None and verdict.passed:
                attempts.append(Attempt(number, provenance.agent, provenance.model, "passed"))
                return Explanation(moment, insight, verdict, tuple(attempts))
            attempts.append(Attempt(number, provenance.agent, provenance.model, "failed", codes))
            feedback = verdict.findings
    return _template(moment, facts, attempts)


def _template(moment: Moment, facts: MatchFacts, attempts: list[Attempt]) -> Explanation:
    number = len(attempts) + 1
    insight = template_insight(moment, facts, attempt=number)
    verdict = verify(insight, moment, facts)
    outcome: Outcome = "passed" if verdict.passed else "failed"
    record = Attempt(
        number,
        insight.provenance.agent,
        insight.provenance.model,
        outcome,
        tuple(f.code for f in verdict.findings),
    )
    return Explanation(moment, insight if verdict.passed else None, verdict, (*attempts, record))
