"""A partner's version of a verified insight: the same claims and facts in new words.

A Localizer only rewrites text, so the checks here are structural: the claims, their types and
evidence are the canonical insight's; each claim names exactly the canonical facts, in their roles
(references of different kinds may move, as word order changes in translation, but two clubs, a
scorer and an assist, or a before and after value keep their order); the headline may drop one of
the canonical headline's facts, never add one. Then the text is
checked as any claim is, in the partner's language, against the partner's blocked topics, and
against the length of the graphic it airs in.
"""

from collections.abc import Callable, Iterator, Sequence

from fourth_official_contracts import (
    MAX_FINDINGS,
    MAX_HEADLINE_CHARS,
    MAX_LINE_CHARS,
    Finding,
    FindingCode,
    Insight,
    LocalizedInsight,
    Moment,
    Verdict,
    claim_references,
)
from fourth_official_verifier.facts import MatchFacts
from fourth_official_verifier.render import RenderError, render_insight
from fourth_official_verifier.verify import verify

# The partner's blocked topics a text touches: `fourth_official_policy.blocked_topics_in`.
BlockedTopics = Callable[[str], Sequence[str]]


def _finding(claim_id: str | None, code: FindingCode, detail: str) -> Finding:
    return Finding(claim_id=claim_id, code=code, detail=detail[:200])


def _by_kind(text: str) -> dict[str, list[str]]:
    """Each kind of reference in the order the text names them: who leads whom, before and after."""
    found: dict[str, list[str]] = {}
    for kind, argument in claim_references(text):
        found.setdefault(kind, []).append(argument)
    return found


def _is_subsequence(part: list[str], whole: list[str]) -> bool:
    remaining = iter(whole)
    return all(item in remaining for item in part)


def _keeps(mine: str, theirs: str, *, may_drop: bool) -> bool:
    """Whether `mine` names `theirs`'s facts in their roles. References of different kinds may
    move (word order changes in translation); references of one kind keep their order, so two
    clubs, a scorer and an assist, or a before and after value never swap."""
    have, want = _by_kind(mine), _by_kind(theirs)
    if not set(have) <= set(want) or (not may_drop and set(have) != set(want)):
        return False
    if may_drop:
        return all(_is_subsequence(have[k], want[k]) for k in have)
    return all(have[k] == want[k] for k in want)


def _structure(localized: LocalizedInsight, canonical: Insight) -> Iterator[Finding]:
    if localized.insight_id != canonical.insight_id:
        yield _finding(None, "CLAIMS_CHANGED", "this is not a version of the canonical insight")
        return
    if [c.claim_id for c in localized.claims] != [c.claim_id for c in canonical.claims]:
        yield _finding(None, "CLAIMS_CHANGED", "keep exactly the canonical claims, in order")
        return
    for mine, theirs in zip(localized.claims, canonical.claims, strict=True):
        if (mine.type, mine.evidence) != (theirs.type, theirs.evidence):
            yield _finding(mine.claim_id, "CLAIMS_CHANGED", "keep the claim's type and evidence")
        if not _keeps(mine.text, theirs.text, may_drop=False):
            yield _finding(
                mine.claim_id,
                "REFERENCES_CHANGED",
                "keep exactly the claim's references, each kind in its order",
            )
    # The headline may leave a fact out, never add or repeat one.
    if not _keeps(localized.headline, canonical.headline, may_drop=True):
        yield _finding(
            None, "REFERENCES_CHANGED", "the headline may only drop the canonical headline's facts"
        )


def _blocked(localized: LocalizedInsight, blocked: BlockedTopics) -> Iterator[Finding]:
    texts = [(None, localized.headline)] + [(c.claim_id, c.text) for c in localized.claims]
    for claim_id, text in texts:
        topics = list(blocked(text))
        if topics:
            yield _finding(
                claim_id, "BLOCKED_TOPIC", f"the partner never covers: {', '.join(topics)}"
            )


def _length(localized: LocalizedInsight, facts: MatchFacts) -> Iterator[Finding]:
    try:
        headline, claims = render_insight(localized, facts, localized.locale)
    except RenderError:
        return  # the language checks report what does not resolve
    if len(headline) > MAX_HEADLINE_CHARS:
        yield _finding(
            None, "TOO_LONG", f"the headline must fit in {MAX_HEADLINE_CHARS} characters"
        )
    for claim, text in zip(localized.claims, claims, strict=True):
        if len(text) > MAX_LINE_CHARS:
            yield _finding(
                claim.claim_id, "TOO_LONG", f"each claim must fit in {MAX_LINE_CHARS} characters"
            )


def verify_localized(
    localized: LocalizedInsight,
    canonical: Insight,
    moment: Moment,
    facts: MatchFacts,
    *,
    blocked: BlockedTopics,
) -> Verdict:
    """Whether a partner's version may air: the canonical facts, and nothing else, in words that
    pass the language's checks, the partner's topics and the graphic's length."""
    findings = [
        *_structure(localized, canonical),
        *verify(localized, moment, facts).findings,
        *_blocked(localized, blocked),
        *_length(localized, facts),
    ][:MAX_FINDINGS]
    return Verdict(
        insight_id=canonical.insight_id,
        match_id=localized.match_id,
        passed=not findings,
        findings=tuple(findings),
    )
