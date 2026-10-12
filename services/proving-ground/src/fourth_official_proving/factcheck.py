"""The Proving Ground's fact check: every claim still on air at full time, held against what
finally happened. Code reads the claim's references; no model judges anything here."""

from collections.abc import Iterator, Sequence

from fourth_official_contracts import FailedClaim, Insight, LocalizedInsight, claim_references
from fourth_official_proving.truth import Truth

HEADLINE = "headline"
# The moment that announces a goal ruled out cites that goal: it is what it explains.
EXPLAINS_VOIDS = "var_overturn"


def _reasons(
    text: str, event_ids: Sequence[str], as_of_seq: int, truth: Truth, *, own_evidence: bool
) -> Iterator[str]:
    if own_evidence:
        for event_id in event_ids:
            if event_id in truth.voided:
                yield f"rests on {event_id}, which was ruled out"
    involved = truth.participants(event_ids)
    minutes = truth.minutes(event_ids)
    for kind, argument in claim_references(text):
        if kind == "player" and argument not in involved:
            yield f"names {argument}, who is not credited in its events"
        elif kind == "minute" and int(argument) not in minutes:
            yield f"names minute {argument}, when none of its events happened"
        elif kind == "score":
            published = truth.score_at(as_of_seq, as_published=True)
            final = truth.score_at(as_of_seq)
            if published != final:
                yield (
                    f"states the score as {published[0]}-{published[1]}; "
                    f"it was {final[0]}-{final[1]}"
                )


def _kind(moment_id: str) -> str:
    # `mo-m42-var_overturn-HCY-s1704`: kinds use underscores, never hyphens.
    return moment_id.split("-")[2]


def check_insight(
    insight: Insight | LocalizedInsight, item_id: str, truth: Truth
) -> tuple[FailedClaim, ...]:
    """Every claim of the insight that the truth does not support, and the headline if its own
    references are wrong (it rests on the claims' evidence, which the claims already answer for)."""
    checked = [(c.claim_id, c.text, c.evidence.event_ids) for c in insight.claims]
    everything = tuple(dict.fromkeys(e for c in insight.claims for e in c.evidence.event_ids))
    checked.append((HEADLINE, insight.headline, everything))
    failures = []
    for claim_id, text, event_ids in checked:
        own = claim_id != HEADLINE and _kind(insight.moment_id) != EXPLAINS_VOIDS
        found = _reasons(text, event_ids, insight.as_of_seq, truth, own_evidence=own)
        reasons = tuple(dict.fromkeys(found))
        if reasons:
            failures.append(
                FailedClaim(
                    match_id=insight.match_id,
                    item_id=item_id,
                    claim_id=claim_id,
                    text=text,
                    event_ids=tuple(event_ids),
                    reasons=reasons,
                )
            )
    return tuple(failures)
