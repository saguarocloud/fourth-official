"""Deciding a held item during the match: the decision is the item's next entry on the match's
feed, so every partner screen and stream sees it at once. Each refusal says why, in its own type."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import anyio
import pytest

from fourth_official_contracts import (
    ClockEntry,
    CorrectionAction,
    CorrectionEntry,
    MatchClock,
    TenantItemEntry,
)
from fourth_official_match_data import demo_store
from fourth_official_replay import Decision, Matchday, Partners, ReplayConfig
from fourth_official_replay.errors import (
    CorrectedSinceError,
    FullTimeError,
    NoRoomOnAirError,
    NotAwaitingError,
    ReplayedSinceError,
    UnknownItemError,
)
from fourth_official_replay.partners import EntryBuilder
from paused import Paused
from test_partners import no_wait, partners, template_only

NOW = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)


def during_the_match(
    check: Callable[[Paused], Awaitable[None]], paused: Paused | None = None
) -> None:
    held = paused or Paused()

    async def run() -> None:
        await held.day.start(now=0.0)
        try:
            await held.until_held()
            await check(held)
        finally:
            # Released whatever the check did: a failing check fails the test, never hangs it.
            held.released.set()
            await held.day.wait()

    anyio.run(run)


async def decide(
    paused: Paused, item: TenantItemEntry, decision: str = "approved"
) -> TenantItemEntry:
    return await paused.day.decide(
        "m42",
        item.tenant_id,
        item.overlay.item_id,
        decision,  # type: ignore[arg-type]
        reason="Off tone" if decision == "rejected" else None,
        now=NOW,
        generation=paused.generation,
    )


def corrected_targets(paused: Paused) -> set[str]:
    return {
        e.correction.target_event_id
        for e in paused.day.feed("m42").entries
        if isinstance(e, CorrectionEntry)
    }


def untouched(paused: Paused) -> TenantItemEntry:
    """A held item no correction has touched."""
    targets = corrected_targets(paused)
    return next(
        i
        for i in paused.held()
        if not any(set(c.evidence.event_ids) & targets for c in i.localized.claims)  # type: ignore[union-attr]
    )


def test_an_approval_is_published_on_the_feed_from_the_match_clock() -> None:
    async def check(paused: Paused) -> None:
        item = untouched(paused)
        before = len(paused.day.feed("m42").entries)
        clock = [e for e in paused.day.feed("m42").entries if isinstance(e, ClockEntry)][-1]

        entry = await decide(paused, item)

        assert entry.state == "on_air"
        assert entry.entry_seq == before + 1
        assert paused.day.feed("m42").entries[-1] == entry
        assert (entry.overlay.in_at.period, entry.overlay.in_at.minute) >= (
            clock.clock.period,
            clock.clock.minute,
        )

    during_the_match(check)


def test_an_item_is_decided_once() -> None:
    async def check(paused: Paused) -> None:
        item = untouched(paused)
        await decide(paused, item, "rejected")

        with pytest.raises(NotAwaitingError):
            await decide(paused, item)

    during_the_match(check)


def test_two_editors_deciding_at_once_cannot_both_win() -> None:
    async def check(paused: Paused) -> None:
        item = untouched(paused)
        refused: list[str] = []

        async def attempt(decision: str) -> None:
            try:
                await decide(paused, item, decision)
            except NotAwaitingError:
                refused.append(decision)

        async with anyio.create_task_group() as group:
            group.start_soon(attempt, "approved")
            group.start_soon(attempt, "rejected")

        versions = [
            e
            for e in paused.day.feed("m42").entries
            if isinstance(e, TenantItemEntry) and e.overlay.item_id == item.overlay.item_id
        ]
        assert len(refused) == 1
        assert len(versions) == 2
        assert versions[-1].approval is not None
        assert versions[-1].approval.decision != refused[0]

    during_the_match(check)


def test_an_unknown_item_or_match_is_not_found() -> None:
    async def check(paused: Paused) -> None:
        with pytest.raises(UnknownItemError):
            await paused.day.decide(
                "m42",
                "tribuna-austral",
                "it-tribuna-austral-nothing",
                "approved",
                reason=None,
                now=NOW,
                generation=paused.generation,
            )
        with pytest.raises(UnknownItemError):
            await paused.day.decide(
                "m99", "tribuna-austral", "it-x", "approved", reason=None, now=NOW, generation=1
            )

    during_the_match(check)


def test_after_full_time_a_held_item_can_no_longer_air() -> None:
    day = Matchday(
        demo_store(), template_only, config=ReplayConfig(), sleep=no_wait, partners=partners
    )

    async def run() -> None:
        await day.start(now=0.0)
        await day.wait()
        item = next(
            e
            for e in day.feed("m42").entries
            if isinstance(e, TenantItemEntry) and e.state == "pending_approval"
        )
        with pytest.raises(FullTimeError):
            await day.decide(
                "m42",
                item.tenant_id,
                item.overlay.item_id,
                "approved",
                reason=None,
                now=NOW,
                generation=day.feed("m42").generation,
            )

    anyio.run(run)


def test_a_decision_made_in_another_run_is_refused() -> None:
    async def check(paused: Paused) -> None:
        item = untouched(paused)
        with pytest.raises(ReplayedSinceError):
            await paused.day.decide(
                "m42",
                item.tenant_id,
                item.overlay.item_id,
                "approved",
                reason=None,
                now=NOW,
                generation=paused.generation + 1,
            )

    during_the_match(check)


def test_a_new_run_between_looking_up_and_publishing_wins() -> None:
    class Slow(Partners):
        async def decide(
            self,
            item: TenantItemEntry,
            decision: Decision,
            *,
            reason: str | None,
            at: MatchClock,
            now: datetime,
        ) -> EntryBuilder:
            build = await super().decide(item, decision, reason=reason, at=at, now=now)
            await paused.day.feed("m42").reset()  # a restart lands mid-decision
            return build

    paused = Paused(factory=lambda: Slow(partners()._partners, localizer=None))

    async def check(held: Paused) -> None:
        item = untouched(held)
        with pytest.raises(ReplayedSinceError):
            await decide(held, item)
        assert held.day.feed("m42").entries == ()

    during_the_match(check, paused)


def test_an_approval_with_no_room_on_air_waits() -> None:
    made: list[Partners] = []

    def factory() -> Partners:
        made.append(partners())
        return made[-1]

    async def check(paused: Paused) -> None:
        item = untouched(paused)
        clock = [e for e in paused.day.feed("m42").entries if isinstance(e, ClockEntry)][-1]
        mine = made[0]
        while await mine._place(item.tenant_id, "lower_third", clock.clock) is not None:
            pass

        with pytest.raises(NoRoomOnAirError):
            await decide(paused, item)
        assert item in paused.held()

    during_the_match(check, Paused(factory=factory))


class NoDesk(Partners):
    """Partners whose corrections desk does nothing: the decision guard is the last line."""

    async def correct(
        self, *args: object, **kwargs: object
    ) -> tuple[list[EntryBuilder], list[CorrectionAction]]:
        return [], []


def test_an_item_a_correction_has_since_touched_cannot_air() -> None:
    # The desk retracts such an item at once; should a decision arrive first, it is refused.
    async def check(paused: Paused) -> None:
        targets = corrected_targets(paused)
        touched = next(
            i
            for i in paused.held()
            if any(set(c.evidence.event_ids) & targets for c in i.localized.claims)  # type: ignore[union-attr]
        )

        with pytest.raises(CorrectedSinceError):
            await decide(paused, touched)
        assert touched in paused.held()

    no_desk = Paused(factory=lambda: NoDesk(partners()._partners, localizer=None))
    during_the_match(check, no_desk)


def test_the_desk_retracts_a_held_item_a_correction_touched() -> None:
    async def check(paused: Paused) -> None:
        targets = corrected_targets(paused)
        for item in paused.held():
            evidence = {e for c in item.localized.claims for e in c.evidence.event_ids}  # type: ignore[union-attr]
            assert not evidence & targets

    during_the_match(check)
