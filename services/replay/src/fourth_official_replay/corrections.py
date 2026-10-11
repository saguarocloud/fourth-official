"""The corrections desk: when the source data changes, everything already published that rests on
the corrected event is found and dealt with, per partner, and the whole of it is reported.

- Found: the canonical insights whose moments or claims rest on the event, and every partner's
  latest version of them. A void does not touch the insight that explains it (the VAR moment).
- Done (`Partners.correct`): see there. Items already off air are left alone.
- Reported: one `correction_report` entry with every action and the time it all took, which the
  Corrections Center replays.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any, Literal

from fourth_official_broadcast import Schedule, lower_third, place
from fourth_official_contracts import (
    AttemptRecord,
    Correction,
    CorrectionAction,
    CorrectionReportEntry,
    EventAmended,
    FeedEntry,
    InsightEntry,
    MatchClock,
    Moment,
    MomentEntry,
    RenderedInsight,
    TenantItemEntry,
    TenantPolicy,
)
from fourth_official_policy import disclose
from fourth_official_stats.prepare import prepare
from fourth_official_verifier import MatchFacts, render_insight, template_localized, verify

# Moments that explain a void: the voided event is part of their story, not a fact they assert.
_EXPLAINS_A_VOID = frozenset({"var_overturn"})
_LIVE_STATES = frozenset({"on_air", "pending_approval"})


def _rests_on(event_ids: set[str], correction: Correction) -> bool:
    return correction.target_event_id in event_ids


def touched(
    entries: Sequence[FeedEntry], correction: Correction, *, only: frozenset[str] | None = None
) -> tuple[tuple[str, ...], tuple[TenantItemEntry, ...]]:
    """The canonical insights resting on the corrected event (only those in `only`, if given),
    and each partner's latest version of them that is still on air or held."""
    moments = {e.moment.moment_id: e.moment for e in entries if isinstance(e, MomentEntry)}
    insight_ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, InsightEntry):
            continue
        insight = entry.insight
        moment = moments.get(insight.moment_id)
        if (
            moment is not None
            and moment.kind in _EXPLAINS_A_VOID
            and correction.kind == "EVENT_VOIDED"
        ):
            continue
        evidence = {e for c in insight.claims for e in c.evidence.event_ids}
        if moment is not None:
            evidence |= set(moment.event_ids)
        if only is not None and insight.insight_id not in only:
            continue
        if _rests_on(evidence, correction) and insight.insight_id not in insight_ids:
            insight_ids.append(insight.insight_id)
    latest: dict[tuple[str, str], TenantItemEntry] = {}
    for entry in entries:
        if not isinstance(entry, TenantItemEntry) or entry.localized is None:
            continue
        if entry.localized.insight_id in insight_ids:
            latest[(entry.tenant_id, entry.localized.insight_id)] = entry
    items = tuple(i for i in latest.values() if i.state in _LIVE_STATES)
    return tuple(insight_ids), items


def corrected_facts(facts: MatchFacts, correction: Correction) -> MatchFacts:
    """The facts with an amendment applied: the event in a new version, which is the one that
    counts. A void is already in the facts' voids, so the facts are returned as they are."""
    if not isinstance(correction, EventAmended):
        return facts
    events = facts.match.events
    target = next((e for e in events if e.event_id == correction.target_event_id), None)
    if target is None:
        return facts
    # Through the wire, as any client would read it, so the amended event is validated in full.
    wire: dict[str, Any] = {
        **target.to_wire(),
        **correction.changes.to_wire(),
        "version": target.version + 1,
    }
    amended = type(target).model_validate_json(json.dumps(wire))
    return replace(facts, match=prepare(facts.match.context, [*events, amended]))


def report_entry(
    correction: Correction,
    insight_ids: Sequence[str],
    actions: Sequence[CorrectionAction],
    *,
    started_at: datetime,
    elapsed_ms: int,
) -> Callable[[int], CorrectionReportEntry]:
    """The report, built for the next number on the feed."""

    def build(entry_seq: int) -> CorrectionReportEntry:
        return CorrectionReportEntry(
            kind="correction_report",
            entry_seq=entry_seq,
            match_id=correction.match_id,
            correction_id=correction.correction_id,
            target_event_id=correction.target_event_id,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            insight_ids=tuple(insight_ids),
            actions=tuple(actions),
        )

    return build


def moments_of(entries: Sequence[FeedEntry]) -> dict[str, Moment]:
    return {e.moment.moment_id: e.moment for e in entries if isinstance(e, MomentEntry)}


def restated(
    item: TenantItemEntry, state: Literal["retracted", "amended"]
) -> Callable[[int], TenantItemEntry]:
    """The item's next entry, off air: pulled (retracted) or replaced by a newer version."""
    wire = item.to_wire()
    return lambda n: TenantItemEntry.model_validate_json(
        json.dumps({**wire, "entrySeq": n, "state": state})
    )


_REGENERATED = AttemptRecord(
    number=1, agent="template", model="none", outcome="passed", findings=(), error=None
)


def regenerated(
    item: TenantItemEntry,
    moment: Moment,
    facts: MatchFacts,
    policy: TenantPolicy,
    *,
    at: MatchClock,
    held: bool,
) -> Callable[[int], TenantItemEntry] | None:
    """The item's next version from the corrected facts: the partner's template, verified again,
    on air from `at` (outside the partner's pace: a correction does not wait its turn), or held
    for an editor. None when no version passes; the item is then pulled instead."""
    old = item.localized
    if old is None:
        return None
    try:
        localized = template_localized(
            moment,
            facts,
            tenant_id=item.tenant_id,
            insight_id=old.insight_id,
            policy_version=policy.version,
            version=old.version + 1,
        )
    except ValueError:
        return None
    if not verify(localized, moment, facts).passed:
        return None
    headline, claims = render_insight(localized, facts, policy.locale)
    disclosure = disclose(policy, item.item_kind, None)
    timing = place(Schedule(max_per_minute=60), "lower_third", at)[1]
    if disclosure is None or timing is None:  # pragma: no cover - narrative is always disclosed
        return None
    overlay = lower_third(
        localized, (headline, claims), disclosure, timing, supersedes=item.overlay.item_id
    )
    return lambda n: TenantItemEntry(
        kind="tenant_item",
        entry_seq=n,
        match_id=item.match_id,
        tenant_id=item.tenant_id,
        item_kind=item.item_kind,
        approval_required=held,
        state="pending_approval" if held else "on_air",
        localized=localized,
        rendered=RenderedInsight(headline=headline, claims=claims),
        overlay=overlay,
        attempts=(_REGENERATED,),
        approval=None,
    )
