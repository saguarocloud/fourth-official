"""Localise a verified insight for one partner: the model rewrites words, code keeps the facts.

The Localizer's structured output is text only: a headline and each claim's text, by claim id.
Code copies each claim's type and evidence from the canonical insight, so a draft cannot cite
anything new, and `verify_localized` checks that every fact survived in its role. A refused
draft gets one retry with itself and the findings; then the partner's template stands in.
An English partner airs the canonical words as they are, with no model call: they keep the
canonical provenance (the words are the Analyst's), and the check is recorded as an attempt by
the localizer with no model.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from fourth_official_contracts import (
    Claim,
    Finding,
    Insight,
    LocalizedInsight,
    Moment,
    Provenance,
    TenantPolicy,
    Verdict,
    item_id_for,
)
from fourth_official_explain.metering import TokenCount, collecting, totals
from fourth_official_explain.pipeline import PROGRAMMING_ERRORS, Attempt, Outcome
from fourth_official_verifier import (
    BlockedTopics,
    MatchFacts,
    template_localized,
    verify,
    verify_localized,
)

RETRIES = 1
TIMEOUT_SECONDS = 15.0
logger = logging.getLogger(__name__)


class LocalizedClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(description="The canonical claim's id, unchanged")
    text: str = Field(description="The claim in the partner's language, with the same references")


class LocalizedDraft(BaseModel):
    """What the Localizer writes: words only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    headline: str = Field(description="A short headline in the partner's language")
    claims: list[LocalizedClaimDraft] = Field(description="Every canonical claim, in order")


@dataclass(frozen=True, slots=True)
class LocalizationRequest:
    canonical: Insight
    policy: TenantPolicy
    attempt: int
    # What the Verifier found wrong with the previous draft, and that draft.
    feedback: tuple[Finding, ...] = ()
    previous: LocalizedDraft | None = None


class Localizer(Protocol):
    @property
    def provenance(self) -> Provenance: ...

    async def draft(self, request: LocalizationRequest) -> LocalizedDraft: ...


@dataclass(frozen=True, slots=True)
class Localization:
    # None only if even the partner's template failed its checks: nothing airs for the moment.
    localized: LocalizedInsight | None
    verdict: Verdict
    attempts: tuple[Attempt, ...]


def to_localized(
    draft: LocalizedDraft,
    canonical: Insight,
    *,
    policy: TenantPolicy,
    provenance: Provenance,
    version: int,
) -> LocalizedInsight:
    """The partner's version the draft describes: its words, the canonical claims' types and
    evidence. Raises `ValueError` (pydantic's `ValidationError` included) if the draft does not
    rewrite exactly the canonical claims or breaks the contract."""
    if [c.claim_id for c in draft.claims] != [c.claim_id for c in canonical.claims]:
        raise ValueError("the draft must rewrite exactly the canonical claims, in order")
    return LocalizedInsight(
        item_id=item_id_for(policy.tenant_id, canonical.insight_id, version=version),
        tenant_id=policy.tenant_id,
        locale=policy.locale,
        insight_id=canonical.insight_id,
        match_id=canonical.match_id,
        moment_id=canonical.moment_id,
        as_of_seq=canonical.as_of_seq,
        version=version,
        headline=draft.headline,
        claims=tuple(
            Claim(
                claim_id=mine.claim_id, type=theirs.type, text=mine.text, evidence=theirs.evidence
            )
            for mine, theirs in zip(draft.claims, canonical.claims, strict=True)
        ),
        provenance=provenance,
        policy_version=policy.version,
    )


def _malformed(canonical: Insight, error: ValueError) -> Verdict:
    detail = "the draft cannot be built: " + str(error).splitlines()[0]
    return Verdict(
        insight_id=canonical.insight_id,
        match_id=canonical.match_id,
        passed=False,
        findings=(Finding(claim_id=None, code="MALFORMED_INSIGHT", detail=detail[:200]),),
    )


@dataclass(frozen=True, slots=True)
class _Job:
    """One canonical insight for one partner, and what decides whether its version airs."""

    canonical: Insight
    moment: Moment
    facts: MatchFacts
    policy: TenantPolicy
    blocked: BlockedTopics


def _template(job: _Job, attempts: list[Attempt]) -> Localization:
    localized = template_localized(
        job.moment,
        job.facts,
        tenant_id=job.policy.tenant_id,
        insight_id=job.canonical.insight_id,
        policy_version=job.policy.version,
    )
    verdict = verify(localized, job.moment, job.facts)
    texts = (localized.headline, *(c.text for c in localized.claims))
    touched = [topic for text in texts for topic in job.blocked(text)]
    passed = verdict.passed and not touched
    record = Attempt(
        len(attempts) + 1,
        localized.provenance.agent,
        localized.provenance.model,
        "passed" if passed else "failed",
        tuple(f.code for f in verdict.findings) + (("BLOCKED_TOPIC",) if touched else ()),
    )
    return Localization(localized if passed else None, verdict, (*attempts, record))


def _english(job: _Job) -> Localization:
    """An English partner airs the canonical words, checked against its own policy."""
    canonical = job.canonical
    draft = LocalizedDraft(
        headline=canonical.headline,
        claims=[LocalizedClaimDraft(claim_id=c.claim_id, text=c.text) for c in canonical.claims],
    )
    localized = to_localized(
        draft, canonical, policy=job.policy, provenance=canonical.provenance, version=1
    )
    verdict = verify_localized(localized, canonical, job.moment, job.facts, blocked=job.blocked)
    # No model writes these words: the check of the canonical text is the one attempt.
    outcome: Outcome = "passed" if verdict.passed else "failed"
    check = Attempt(1, "localizer", "none", outcome, tuple(f.code for f in verdict.findings))
    if verdict.passed:
        return Localization(localized, verdict, (check,))
    return _template(job, [check])


def _check(
    job: _Job, draft: LocalizedDraft, provenance: Provenance
) -> tuple[LocalizedInsight | None, Verdict]:
    try:
        localized = to_localized(
            draft, job.canonical, policy=job.policy, provenance=provenance, version=1
        )
    except ValueError as broken:
        return None, _malformed(job.canonical, broken)
    return localized, verify_localized(
        localized, job.canonical, job.moment, job.facts, blocked=job.blocked
    )


async def _drafts(
    job: _Job, localizer: Localizer, *, retries: int, timeout: float, attempts: list[Attempt]
) -> Localization | None:
    """Draft and check up to `1 + retries` times; None if nothing passed."""
    provenance = localizer.provenance
    feedback: tuple[Finding, ...] = ()
    previous: LocalizedDraft | None = None
    for _ in range(1 + retries):
        number = len(attempts) + 1
        request = LocalizationRequest(job.canonical, job.policy, number, feedback, previous)
        spent: list[TokenCount] = []
        try:
            with collecting() as spent:
                async with asyncio.timeout(timeout):
                    draft = await localizer.draft(request)
        except PROGRAMMING_ERRORS:
            raise
        except Exception as failure:
            logger.warning(
                "localizer failed on attempt %d for %s (%s)",
                number,
                job.canonical.insight_id,
                job.policy.tenant_id,
                exc_info=failure,
            )
            tokens_in, tokens_out = totals(spent)
            attempts.append(
                Attempt(
                    number,
                    provenance.agent,
                    provenance.model,
                    "error",
                    error=type(failure).__name__,
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                )
            )
            return None
        tokens_in, tokens_out = totals(spent)
        localized, verdict = _check(job, draft, provenance)
        passed = localized is not None and verdict.passed
        codes = () if passed else tuple(f.code for f in verdict.findings)
        attempts.append(
            Attempt(
                number,
                provenance.agent,
                provenance.model,
                "passed" if passed else "failed",
                codes,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
            )
        )
        if passed and localized is not None:
            return Localization(localized, verdict, tuple(attempts))
        feedback, previous = verdict.findings, draft
    return None


async def localize(  # noqa: PLR0913 - the moment, its insight and the partner, plus the model
    canonical: Insight,
    moment: Moment,
    facts: MatchFacts,
    policy: TenantPolicy,
    *,
    localizer: Localizer | None,
    blocked: BlockedTopics,
    retries: int = RETRIES,
    timeout: float = TIMEOUT_SECONDS,
) -> Localization:
    """The partner's version of a verified insight, and the record of how it was reached."""
    job = _Job(canonical, moment, facts, policy, blocked)
    if policy.locale == "en-GB":
        return _english(job)
    attempts: list[Attempt] = []
    if localizer is not None:
        drafted = await _drafts(job, localizer, retries=retries, timeout=timeout, attempts=attempts)
        if drafted is not None:
            return drafted
    return _template(job, attempts)


def blocked_nothing(text: str) -> Sequence[str]:
    """For tests and English-only runs: no topic is blocked."""
    return ()
