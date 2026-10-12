"""The Proving Ground's measures, computed by code from runs of the pipeline (plan §9.2).

Every measure is a count of cases: the scorecard keeps the counts and readers compute the rate,
so a percentage is never written down by anything that could get it wrong.
"""

import math
from collections.abc import Iterable, Sequence

from fourth_official_contracts import (
    FailedClaim,
    InsightEntry,
    Latency,
    MomentEntry,
    Ratio,
    StorylineTruth,
    TenantItemEntry,
    TenantPolicy,
)
from fourth_official_contracts.moments import EVENT_MOMENTS
from fourth_official_policy import blocked_topics_in, bundled_store, disclose
from fourth_official_proving.factcheck import EXPLAINS_VOIDS, HEADLINE, check_insight
from fourth_official_proving.runner import MatchRun

# An event storyline is surfaced by a moment within two minutes of it (plan §9.2). A change of
# style needs sustained five-minute windows to show, so it may be found up to ten minutes later.
EVENT_WINDOW = 2
SHIFT_WINDOW = 10
# Storylines the pipeline is built to surface as moments. A reassigned scorer arrives as a
# correction and is measured by `corrections_carried`; other style changes have no rule yet.
SURFACED_KINDS = frozenset({"goal", "red_card", "var_overturn", "pressing_collapse"})
# Moments shown by events (a goal, a big chance, a red card, a VAR decision) happened, so an
# insight about one is about a real moment. A moment read from a metric moving (a press, a swing
# of momentum, a change of shape) is a story only if one was planted.
KEY_KINDS = EVENT_MOMENTS
P50, P95 = 50, 95


def _every_item(run: MatchRun) -> list[TenantItemEntry]:
    """Each partner item once, as its latest version: score bugs and straps included."""
    latest: dict[str, TenantItemEntry] = {}
    for entry in run.entries:
        if isinstance(entry, TenantItemEntry):
            latest[entry.overlay.item_id] = entry
    return list(latest.values())


def _latest_items(run: MatchRun) -> list[TenantItemEntry]:
    """Each narrative partner item once, as its latest version."""
    return [i for i in _every_item(run) if i.localized is not None]


def _insights(run: MatchRun) -> dict[str, InsightEntry]:
    return {e.insight.insight_id: e for e in run.entries if isinstance(e, InsightEntry)}


def supported_claims(runs: Iterable[MatchRun]) -> tuple[Ratio, tuple[FailedClaim, ...]]:
    """Claims partners still air at full time, in their own words, that the truth supports; and
    every one it does not."""
    total = 0
    failures: list[FailedClaim] = []
    for run in runs:
        for item in _latest_items(run):
            if item.state != "on_air" or item.localized is None:
                continue
            total += len(item.localized.claims)
            failures.extend(check_insight(item.localized, item.overlay.item_id, run.truth))
    failed = len({(f.item_id, f.claim_id) for f in failures if f.claim_id != HEADLINE})
    return Ratio(hit=total - failed, of=total), tuple(failures)


def _moments(run: MatchRun) -> list[MomentEntry]:
    return [e for e in run.entries if isinstance(e, MomentEntry)]


def _surfaces(story: StorylineTruth, entry: MomentEntry) -> bool:
    moment = entry.moment
    if (moment.kind, moment.club) != (story.kind, story.club):
        return False
    if story.event_ids:
        if set(moment.event_ids) & set(story.event_ids):
            return True
        return abs(moment.clock.minute - story.minute) <= EVENT_WINDOW
    return story.minute <= moment.clock.minute <= story.minute + SHIFT_WINDOW


def storyline_recall(runs: Iterable[MatchRun]) -> Ratio:
    """Planted storylines that a published insight explains."""
    hit = of = 0
    for run in runs:
        explained = {e.insight.moment_id for e in _insights(run).values()}
        moments = [m for m in _moments(run) if m.moment.moment_id in explained]
        for story in run.ground_truth.storylines:
            if story.kind not in SURFACED_KINDS:
                continue
            of += 1
            hit += any(_surfaces(story, m) for m in moments)
    return Ratio(hit=hit, of=of)


def key_moment_precision(runs: Iterable[MatchRun]) -> Ratio:
    """Published insights about a real moment: one a storyline planted, or one shown by events."""
    hit = of = 0
    for run in runs:
        moments = {m.moment.moment_id: m for m in _moments(run)}
        for entry in _insights(run).values():
            moment = moments.get(entry.insight.moment_id)
            if moment is None:
                continue
            of += 1
            planted = any(_surfaces(s, moment) for s in run.ground_truth.storylines)
            hit += planted or moment.moment.kind in KEY_KINDS
    return Ratio(hit=hit, of=of)


def _policies() -> dict[str, TenantPolicy]:
    return {loaded.policy.tenant_id: loaded.policy for loaded in bundled_store().all()}


def _breaks_policy(item: TenantItemEntry, policy: TenantPolicy) -> bool:
    text = " ".join([item.rendered.headline, *item.rendered.claims]) if item.rendered else ""
    if blocked_topics_in(text, policy):
        return True
    approved = item.approval is not None and item.approval.decision == "approved"
    if item.approval_required and not approved:
        return True
    expected = disclose(policy, item.item_kind, item.approval)
    return item.overlay.disclosure != expected


def policy_violations(runs: Iterable[MatchRun]) -> int:
    """Partner items on air at full time that their partner's policy forbids: a blocked topic,
    held for approval but aired, or disclosed other than the policy says."""
    policies = _policies()
    return sum(
        _breaks_policy(item, policies[item.tenant_id])
        for run in runs
        for item in _every_item(run)
        if item.state == "on_air"
    )


def model_written(runs: Iterable[MatchRun]) -> Ratio:
    entries = [e for run in runs for e in _insights(run).values()]
    by_model = sum(e.insight.provenance.produced_by == "model" for e in entries)
    return Ratio(hit=by_model, of=len(entries))


def first_attempt_pass(runs: Iterable[MatchRun]) -> Ratio:
    """Model-written insights whose first attempt passed the Verifier."""
    written = [
        e
        for run in runs
        for e in _insights(run).values()
        if e.insight.provenance.produced_by == "model"
    ]
    first = sum(bool(e.attempts) and e.attempts[0].outcome == "passed" for e in written)
    return Ratio(hit=first, of=len(written))


def corrections_carried(runs: Iterable[MatchRun]) -> Ratio:
    """Partner items resting on a corrected event, which the corrections desk pulled or replaced
    (as finally standing at full time). Whenever they were published: the desk also reaches items
    published after their correction (ADR-012). A version the desk remade is the replacement, not
    a miss, and the VAR decision's own insight cites the goal it rules out."""
    hit = of = 0
    for run in runs:
        insights = _insights(run)
        kinds = {m.moment.moment_id: m.moment.kind for m in _moments(run)}
        corrected = {c.target_event_id for c in run.record.corrections}
        for item in _latest_items(run):
            canonical = insights.get(item.localized.insight_id) if item.localized else None
            if item.overlay.supersedes is not None or canonical is None:
                continue
            if kinds.get(canonical.insight.moment_id) == EXPLAINS_VOIDS:
                continue
            cited = {e for c in canonical.insight.claims for e in c.evidence.event_ids}
            if not cited & corrected:
                continue
            of += 1
            hit += item.state in ("retracted", "amended")
    return Ratio(hit=hit, of=of)


def _percentile(values: Sequence[float], percent: int) -> float:
    ordered = sorted(values)
    rank = max(0, math.ceil(percent / 100 * len(ordered)) - 1)
    return round(ordered[rank], 1)


def latency(runs: Iterable[MatchRun]) -> Latency | None:
    """Time to explain a moment (nearest-rank percentiles), when a model wrote anything."""
    measured = list(runs)
    if model_written(measured).hit == 0:
        return None
    timings = [t for run in measured for t in run.explain_ms]
    return Latency(p50=_percentile(timings, P50), p95=_percentile(timings, P95))
