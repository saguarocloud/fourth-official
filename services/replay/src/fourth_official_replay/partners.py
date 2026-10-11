"""Each partner's items, from what the replay publishes: every verified insight in the partner's
language and voice, every correction as a strap, every change of score on the score bug.

For each partner, an insight is localised (and verified again), routed to an editor where the
partner's policy says so, labelled as its disclosure mode requires, and timed by the director.
Partners are served concurrently, and a failure for one is logged and stays with it.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial

from fourth_official_broadcast import (
    Schedule,
    Timing,
    correction_strap,
    correction_strap_text,
    lower_third,
    place,
    score_bug,
)
from fourth_official_contracts import (
    AttemptRecord,
    ClubCode,
    Correction,
    Insight,
    ItemKind,
    MatchClock,
    Moment,
    OverlaySpec,
    RenderedInsight,
    Template,
    TenantId,
    TenantItemEntry,
    TenantPolicy,
)
from fourth_official_explain import Attempt
from fourth_official_explain.localize import Localizer, localize
from fourth_official_policy import approval_required, disclose
from fourth_official_verifier import BlockedTopics, MatchFacts, render_insight

logger = logging.getLogger(__name__)
# Builds a partner's feed entry once the log assigns its position.
EntryBuilder = Callable[[int], TenantItemEntry]


@dataclass(frozen=True, slots=True)
class Partner:
    policy: TenantPolicy
    # The partner's blocked topics a text touches (`fourth_official_policy.blocked_topics_in`).
    blocked: BlockedTopics


def _records(attempts: Sequence[Attempt]) -> tuple[AttemptRecord, ...]:
    return tuple(
        AttemptRecord(
            number=a.number,
            agent=a.agent,
            model=a.model,
            outcome=a.outcome,
            findings=a.findings,  # type: ignore[arg-type]
            error=a.error,
        )
        for a in attempts
    )


def _data_entry(
    entry_seq: int, *, match_id: str, kind: ItemKind, overlay: OverlaySpec
) -> TenantItemEntry:
    """A graphic no agent wrote: a correction strap or the score bug, never held."""
    return TenantItemEntry(
        kind="tenant_item",
        entry_seq=entry_seq,
        match_id=match_id,
        tenant_id=overlay.tenant_id,
        item_kind=kind,
        approval_required=False,
        state="on_air",
        localized=None,
        rendered=None,
        overlay=overlay,
        attempts=(),
        approval=None,
    )


class Partners:
    """One match's items for each partner. Holds each partner's director schedule."""

    def __init__(self, partners: Sequence[Partner], *, localizer: Localizer | None) -> None:
        self._partners = tuple(partners)
        self._localizer = localizer
        self._schedules: dict[TenantId, Schedule] = {
            p.policy.tenant_id: Schedule(max_per_minute=p.policy.max_items_per_minute)
            for p in self._partners
        }
        self._lock = asyncio.Lock()

    async def _place(
        self, tenant_id: TenantId, template: Template, at: MatchClock
    ) -> Timing | None:
        async with self._lock:
            schedule, timing = place(self._schedules[tenant_id], template, at)
            self._schedules[tenant_id] = schedule
            return timing

    async def insight(
        self, insight: Insight, moment: Moment, facts: MatchFacts, at: MatchClock
    ) -> list[EntryBuilder]:
        """Each partner's version of a verified insight, published as it is ready."""
        found = await asyncio.gather(
            *(self._insight(p, insight, moment=moment, facts=facts, at=at) for p in self._partners),
            return_exceptions=True,
        )
        return self._kept(found, f"insight {insight.insight_id}")

    async def _insight(
        self,
        partner: Partner,
        insight: Insight,
        *,
        moment: Moment,
        facts: MatchFacts,
        at: MatchClock,
    ) -> EntryBuilder | None:
        policy = partner.policy
        result = await localize(
            insight, moment, facts, policy, localizer=self._localizer, blocked=partner.blocked
        )
        localized = result.localized
        if localized is None:
            logger.warning("nothing passed for %s at %s", policy.tenant_id, insight.insight_id)
            return None
        headline, claims = render_insight(localized, facts, policy.locale)
        held = approval_required(policy, "insight")
        # A held item does not take an on-air slot; it keeps the timing it would have had.
        timing = (
            place(Schedule(max_per_minute=60), "lower_third", at)[1]
            if held
            else await self._place(policy.tenant_id, "lower_third", at)
        )
        if timing is None:
            logger.info("%s had no room for %s", policy.tenant_id, insight.insight_id)
            return None
        disclosure = disclose(policy, "insight", None)
        if disclosure is None:  # pragma: no cover - narrative is always disclosed
            raise ValueError("an insight is always disclosed")
        overlay = lower_third(localized, (headline, claims), disclosure, timing)
        attempts = _records(result.attempts)
        return lambda n: TenantItemEntry(
            kind="tenant_item",
            entry_seq=n,
            match_id=insight.match_id,
            tenant_id=policy.tenant_id,
            item_kind="insight",
            approval_required=held,
            state="pending_approval" if held else "on_air",
            localized=localized,
            rendered=RenderedInsight(headline=headline, claims=claims),
            overlay=overlay,
            attempts=attempts,
            approval=None,
        )

    async def correction(
        self, correction: Correction, facts: MatchFacts, at: MatchClock
    ) -> list[EntryBuilder]:
        """A strap for every partner: a correction is never held for approval."""
        found = await asyncio.gather(
            *(self._correction(p, correction, facts, at) for p in self._partners),
            return_exceptions=True,
        )
        return self._kept(found, f"correction {correction.correction_id}")

    async def _correction(
        self, partner: Partner, correction: Correction, facts: MatchFacts, at: MatchClock
    ) -> EntryBuilder | None:
        tenant_id = partner.policy.tenant_id
        text = correction_strap_text(correction, facts, partner.policy.locale)
        timing = await self._place(tenant_id, "correction_strap", at)
        if timing is None:
            return None
        overlay = correction_strap(
            tenant_id=tenant_id,
            item_id=f"it-{tenant_id}-{correction.correction_id}",
            text=text,
            timing=timing,
        )
        return partial(
            _data_entry, match_id=correction.match_id, kind="correction", overlay=overlay
        )

    async def score(
        self,
        *,
        match_id: str,
        as_of_seq: int,
        home: ClubCode,
        away: ClubCode,
        score: tuple[int, int],
        at: MatchClock,
    ) -> list[EntryBuilder]:
        """The score bug for every partner, on each change of score."""
        found: list[EntryBuilder | BaseException | None] = []
        for partner in self._partners:
            tenant_id = partner.policy.tenant_id
            try:
                timing = await self._place(tenant_id, "score_bug", at)
                if timing is None:
                    found.append(None)
                    continue
                overlay = score_bug(
                    tenant_id=tenant_id,
                    item_id=f"it-{tenant_id}-score-{match_id}-s{as_of_seq:04d}",
                    home=home,
                    away=away,
                    score=score,
                    clock=at,
                    timing=timing,
                )
            except Exception as failure:
                found.append(failure)
                continue
            found.append(partial(_data_entry, match_id=match_id, kind="score", overlay=overlay))
        return self._kept(found, f"score at {as_of_seq}")

    def _kept(
        self, found: Sequence[EntryBuilder | BaseException | None], what: str
    ) -> list[EntryBuilder]:
        kept: list[EntryBuilder] = []
        for partner, outcome in zip(self._partners, found, strict=False):
            if isinstance(outcome, BaseException):
                if not isinstance(outcome, Exception):
                    raise outcome  # cancellation and other control flow always propagate
                logger.error("%s failed for %s", what, partner.policy.tenant_id, exc_info=outcome)
            elif outcome is not None:
                kept.append(outcome)
        return kept
