"""Each partner's items, from what the replay publishes: every verified insight in the partner's
language and voice, every correction as a strap, every change of score on the score bug.

For each partner, an insight is localised (and verified again), routed to an editor where the
partner's policy says so, labelled as its disclosure mode requires, and timed by the director.
Partners are served concurrently, and a failure for one is logged and stays with it.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from functools import partial
from typing import Literal

from pydantic import ValidationError

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
    Approval,
    AttemptRecord,
    ClubCode,
    Correction,
    CorrectionAction,
    FeedEntry,
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
    item_id_for,
)
from fourth_official_explain import Attempt
from fourth_official_explain.localize import Localizer, localize
from fourth_official_policy import approval_required, disclose
from fourth_official_replay.corrections import moments_of, regenerated, restated, touched
from fourth_official_replay.errors import DecisionError, NoRoomOnAirError, NotAwaitingError
from fourth_official_verifier import BlockedTopics, MatchFacts, render_insight

logger = logging.getLogger(__name__)
Decision = Literal["approved", "rejected"]
# Localisations in flight at once, across the match's partners and moments.
DEFAULT_CONCURRENCY = 3
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


# A partner as its policy stands now: read at every item, so a policy changed mid-match governs
# the next item without a restart (Policy Studio).
PartnerSource = Callable[[TenantId], Partner]


class Partners:
    """One match's items for each partner. Holds each partner's director schedule."""

    def __init__(
        self,
        partners: Sequence[Partner],
        *,
        localizer: Localizer | None,
        concurrency: int = DEFAULT_CONCURRENCY,
        source: PartnerSource | None = None,
    ) -> None:
        self._partners = tuple(partners)
        self._source = source
        self._localizer = localizer
        # Bounds the Localizer's model calls in flight, however many moments arrive at once.
        self._slots = asyncio.Semaphore(concurrency)
        self._schedules: dict[TenantId, Schedule] = {
            p.policy.tenant_id: Schedule(max_per_minute=p.policy.max_items_per_minute)
            for p in self._partners
        }
        self._lock = asyncio.Lock()

    def _now(self, partner: Partner) -> Partner:
        """The partner as its policy stands now: from the live source if there is one."""
        return self._source(partner.policy.tenant_id) if self._source else partner

    def _policy(self, tenant_id: TenantId) -> TenantPolicy | None:
        for partner in self._partners:
            if partner.policy.tenant_id == tenant_id:
                return self._now(partner).policy
        return None

    async def _place(
        self, tenant_id: TenantId, template: Template, at: MatchClock
    ) -> Timing | None:
        async with self._lock:
            schedule = self._schedules[tenant_id]
            policy = self._policy(tenant_id)
            if policy is not None and template not in policy.templates:
                # The partner's allow-list governs what airs, as Policy Studio last set it.
                return None
            if policy is not None and policy.max_items_per_minute != schedule.max_per_minute:
                # The director keeps what is on air and paces what comes next by the new limit.
                schedule = replace(schedule, max_per_minute=policy.max_items_per_minute)
            schedule, timing = place(schedule, template, at)
            self._schedules[tenant_id] = schedule
            return timing

    async def insight(
        self, insight: Insight, moment: Moment, facts: MatchFacts, at: MatchClock
    ) -> list[EntryBuilder]:
        """Each partner's version of a verified insight, published as it is ready."""
        found = await asyncio.gather(
            *(
                self._insight(self._now(p), insight, moment=moment, facts=facts, at=at)
                for p in self._partners
            ),
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
        async with self._slots:
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

    async def decide(
        self,
        item: TenantItemEntry,
        decision: Decision,
        *,
        reason: str | None,
        at: MatchClock,
        now: datetime,
    ) -> EntryBuilder:
        """The held item's next entry once its partner's duty editor decides: approved, it airs
        from `at` (the match clock now), or the first free slot after it, labelled as reviewed
        where the policy says so; rejected, it stays off air with the reason. The words are the
        ones the editor saw, unchanged."""
        if item.state != "pending_approval" or item.localized is None or item.rendered is None:
            raise NotAwaitingError
        policy = self._policy(item.tenant_id)
        if policy is None:
            raise NotAwaitingError
        try:
            approval = Approval(
                editor=policy.duty_editor, decided_at=now, decision=decision, reason=reason
            )
        except ValidationError:
            # The API checks reasons first; this keeps any other caller to the contract.
            raise DecisionError("a rejection needs a reason of one line") from None
        if decision == "rejected":
            overlay = item.overlay
        else:
            timing = await self._place(policy.tenant_id, "lower_third", at)
            if timing is None:
                raise NoRoomOnAirError
            disclosure = disclose(policy, item.item_kind, approval)
            if disclosure is None:  # pragma: no cover - narrative is always disclosed
                raise ValueError("an insight is always disclosed")
            rendered = item.rendered
            # An approved amendment still says which version it replaces.
            overlay = lower_third(
                item.localized,
                (rendered.headline, rendered.claims),
                disclosure,
                timing,
                supersedes=item.overlay.supersedes,
            )
        state: Literal["on_air", "rejected"] = "on_air" if decision == "approved" else "rejected"
        # Built through the contract, not copied, so the decided item is checked like any other.
        return lambda n: TenantItemEntry(
            kind="tenant_item",
            entry_seq=n,
            match_id=item.match_id,
            tenant_id=item.tenant_id,
            item_kind=item.item_kind,
            approval_required=item.approval_required,
            state=state,
            localized=item.localized,
            rendered=item.rendered,
            overlay=overlay,
            attempts=item.attempts,
            approval=approval,
        )

    async def correct(
        self,
        correction: Correction,
        entries: Sequence[FeedEntry],
        facts: MatchFacts,
        at: MatchClock,
        *,
        only: frozenset[str] | None = None,
        skip: frozenset[str] = frozenset(),
    ) -> tuple[list[EntryBuilder], list[CorrectionAction]]:
        """What each partner's items resting on a corrected event become, by its policy.

        - Held for an editor: pulled; it can never air.
        - On air, after a void: pulled everywhere; the fact no longer exists.
        - On air, after an amendment: `auto-amend` airs a new version from the corrected facts;
          `escalate` holds a new version for an editor; `retract-and-notify` pulls it. A new
          version that cannot be made (or does not verify) is pulled instead.
        `facts` are the corrected facts (`corrections.corrected_facts`); `only` limits the work
        to those canonical insights, and items in `skip` (already dealt with) are left alone."""
        _, found = touched(entries, correction, only=only)
        items = [i for i in found if i.overlay.item_id not in skip]
        moments = moments_of(entries)
        builders: list[EntryBuilder] = []
        actions: list[CorrectionAction] = []
        for item in items:
            policy = self._policy(item.tenant_id)
            if policy is None or item.localized is None:
                continue
            behaviour = policy.correction_behaviour
            was: Literal["on_air", "pending_approval"] = (
                "pending_approval" if item.state == "pending_approval" else "on_air"
            )
            moment = moments.get(item.localized.moment_id)
            new = None
            amendable = was == "on_air" and correction.kind == "EVENT_AMENDED"
            if amendable and moment is not None and behaviour != "retract-and-notify":
                try:
                    new = regenerated(
                        item, moment, facts, policy, at=at, held=behaviour == "escalate"
                    )
                except Exception:
                    # A version that cannot be made is pulled rather than left on air.
                    logger.exception("could not regenerate %s", item.overlay.item_id)
            if new is None:
                builders.append(restated(item, "retracted"))
                action: Literal["retracted", "amended", "escalated"] = "retracted"
                new_id = None
            else:
                builders += [restated(item, "amended"), new]
                action = "escalated" if behaviour == "escalate" else "amended"
                new_id = item_id_for(
                    item.tenant_id, item.localized.insight_id, version=item.localized.version + 1
                )
            actions.append(
                CorrectionAction(
                    tenant_id=item.tenant_id,
                    locale=policy.locale,
                    insight_id=item.localized.insight_id,
                    item_id=item.overlay.item_id,
                    was=was,
                    action=action,
                    new_item_id=new_id,
                )
            )
        return builders, actions

    async def correction(
        self, correction: Correction, facts: MatchFacts, at: MatchClock
    ) -> list[EntryBuilder]:
        """A strap for every partner: a correction is never held for approval."""
        found = await asyncio.gather(
            *(self._correction(self._now(p), correction, facts, at) for p in self._partners),
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
