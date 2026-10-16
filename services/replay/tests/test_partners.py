"""Every verified insight, correction and score change reaches each partner as its own item: in
its language, labelled as its policy requires, held for an editor where it must be, and timed."""

import time
from collections.abc import Callable
from functools import cache, partial

import anyio

from fourth_official_contracts import FeedEntry, InsightEntry, Moment, Provenance, TenantItemEntry
from fourth_official_explain import Explanation, explain
from fourth_official_explain.localize import LocalizationRequest, LocalizedDraft
from fourth_official_explain.metering import TokenCount, spend
from fourth_official_match_data import demo_store
from fourth_official_policy import blocked_topics_in, bundled_store
from fourth_official_replay import FeedLog, ReplayConfig, replay
from fourth_official_replay.partners import Partner, Partners
from fourth_official_verifier import MatchFacts


async def no_wait(seconds: float) -> None:
    return None


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


def partners() -> Partners:
    return Partners(
        [
            Partner(policy=loaded.policy, blocked=partial(blocked_topics_in, policy=loaded.policy))
            for loaded in bundled_store().all()
        ],
        localizer=None,
    )


@cache
def featured() -> tuple[TenantItemEntry, ...]:
    log = FeedLog("m42")
    anyio.run(
        lambda: replay(
            demo_store().record("m42"),
            log,
            template_only,
            config=ReplayConfig(),
            sleep=no_wait,
            partners=partners(),
        )
    )
    return tuple(e for e in log.entries if isinstance(e, TenantItemEntry))


def of(tenant: str, kind: str) -> list[TenantItemEntry]:
    return [e for e in featured() if e.tenant_id == tenant and e.item_kind == kind]


def test_every_partner_gets_the_insights_in_its_language() -> None:
    for tenant, locale in (
        ("northlight-sport", "en-GB"),
        ("tribuna-austral", "es-MX"),
        ("rheinblick-sport", "de-DE"),
    ):
        items = of(tenant, "insight")
        assert items, tenant
        assert {i.overlay.locale for i in items} == {locale}
        assert all(i.localized is not None and i.localized.locale == locale for i in items)


def test_a_partner_that_requires_an_editor_holds_its_narrative_off_air() -> None:
    held = of("tribuna-austral", "insight")

    # Held until an editor decides; those a correction touched are retracted by the desk.
    assert {i.state for i in held} <= {"pending_approval", "retracted"}
    assert "pending_approval" in {i.state for i in held}
    assert all(i.approval_required for i in held)
    aired = {i.state for i in of("rheinblick-sport", "insight")}
    assert aired <= {"on_air", "retracted", "amended"}
    assert "pending_approval" not in aired


def test_narrative_is_labelled_as_each_policy_requires() -> None:
    labels = {
        tenant: {i.overlay.disclosure.label for i in of(tenant, "insight") if i.overlay.disclosure}
        for tenant in ("northlight-sport", "tribuna-austral", "rheinblick-sport")
    }

    assert labels == {
        "northlight-sport": {"AI-generated"},
        "tribuna-austral": {"Generado con IA"},
        "rheinblick-sport": {"KI-generiert"},
    }


def test_every_correction_airs_as_a_strap_for_every_partner() -> None:
    corrections = demo_store().record("m42").corrections

    for tenant, word in (
        ("northlight-sport", "CORRECTION"),
        ("tribuna-austral", "CORRECCIÓN"),
        ("rheinblick-sport", "KORREKTUR"),
    ):
        straps = of(tenant, "correction")
        assert len(straps) == len(corrections), tenant
        assert all(s.state == "on_air" and s.overlay.disclosure is None for s in straps)
        assert all(s.overlay.content.text.startswith(word) for s in straps)  # type: ignore[union-attr]


def test_the_score_bug_follows_every_change_of_score() -> None:
    bugs = of("rheinblick-sport", "score")
    scores = [b.overlay.content.score for b in bugs]  # type: ignore[union-attr]

    # Kick-off, two goals, the VAR void, the equaliser and the winner.
    assert scores == ["0:0", "1:0", "2:0", "1:0", "1:1", "2:1"]


def test_a_partner_never_receives_another_partner_s_item() -> None:
    for entry in featured():
        assert entry.overlay.tenant_id == entry.tenant_id
        if entry.localized is not None:
            assert entry.localized.tenant_id == entry.tenant_id


def test_a_failure_for_one_partner_leaves_the_others_and_the_match_alone() -> None:
    def broken(text: str) -> list[str]:
        raise RuntimeError("policy service down")

    loaded = {p.policy.tenant_id: p.policy for p in bundled_store().all()}
    flaky = Partners(
        [
            Partner(policy=loaded["tribuna-austral"], blocked=broken),
            Partner(
                policy=loaded["rheinblick-sport"],
                blocked=partial(blocked_topics_in, policy=loaded["rheinblick-sport"]),
            ),
        ],
        localizer=None,
    )
    log = FeedLog("m42")
    anyio.run(
        lambda: replay(
            demo_store().record("m42"), log, template_only, sleep=no_wait, partners=flaky
        )
    )

    items = [e for e in log.entries if isinstance(e, TenantItemEntry)]
    assert {i.tenant_id for i in items if i.item_kind == "insight"} == {"rheinblick-sport"}
    assert log.finished


def test_a_correction_strap_is_timed_at_the_correction_not_before_it() -> None:
    record = demo_store().record("m42")
    events = {e.wall_clock: e for e in record.match.events}
    for strap in of("rheinblick-sport", "correction"):
        correction = next(
            c for c in record.corrections if strap.overlay.item_id.endswith(c.correction_id)
        )
        due = [e for t, e in events.items() if t >= correction.issued_at]
        issued_at = due[0].clock if due else record.match.events[-1].clock
        assert (strap.overlay.in_at.period, strap.overlay.in_at.minute) >= (
            issued_at.period,
            issued_at.minute,
        )


def test_localisations_in_flight_are_limited() -> None:
    running = 0
    peak = 0

    class Counting:
        provenance = Provenance(
            agent="localizer", prompt_version="v1.0", model="fast", produced_by="model"
        )

        async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await anyio.sleep(0.01)
            running -= 1
            raise RuntimeError("no model in tests")

    many = Partners(
        [
            Partner(policy=p.policy, blocked=partial(blocked_topics_in, policy=p.policy))
            for p in bundled_store().all()
        ],
        localizer=Counting(),
        concurrency=2,
    )
    log = FeedLog("m42")
    anyio.run(
        lambda: replay(demo_store().record("m42"), log, template_only, sleep=no_wait, partners=many)
    )

    assert 0 < peak <= 2


def test_a_partner_item_carries_the_tokens_its_localizer_spent() -> None:
    class Failing:
        provenance = Provenance(
            agent="localizer", prompt_version="v1.0", model="fast", produced_by="model"
        )

        async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
            spend(TokenCount(model="fast", input=700, output=90))
            raise RuntimeError("no model in tests")

    metered = Partners(
        [
            Partner(policy=p.policy, blocked=partial(blocked_topics_in, policy=p.policy))
            for p in bundled_store().all()
        ],
        localizer=Failing(),
    )
    log = FeedLog("m42")
    anyio.run(
        lambda: replay(
            demo_store().record("m42"), log, template_only, sleep=no_wait, partners=metered
        )
    )

    tribuna = next(
        e
        for e in log.entries
        if isinstance(e, TenantItemEntry) and e.tenant_id == "tribuna-austral" and e.attempts
    )
    assert (tribuna.attempts[0].input_tokens, tribuna.attempts[0].output_tokens) == (700, 90)
    assert (tribuna.attempts[-1].input_tokens, tribuna.attempts[-1].output_tokens) == (0, 0)


def test_a_partner_s_item_airs_when_it_is_ready_not_when_the_slowest_partner_s_is() -> None:
    class SlowSpanish:
        provenance = Provenance(
            agent="localizer", prompt_version="v1.0", model="fast", produced_by="model"
        )

        async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
            if request.policy.locale == "es-MX":
                await anyio.sleep(1.0)
            raise RuntimeError("no model in tests")

    slow = Partners(
        [
            Partner(policy=p.policy, blocked=partial(blocked_topics_in, policy=p.policy))
            for p in bundled_store().all()
        ],
        localizer=SlowSpanish(),
    )
    log = FeedLog("m42")
    anyio.run(
        lambda: replay(demo_store().record("m42"), log, template_only, sleep=no_wait, partners=slow)
    )

    entries, timing = log.snapshot()
    stamp = dict(zip((e.entry_seq for e in entries), timing.published, strict=True))
    first = next(e for e in entries if isinstance(e, InsightEntry)).insight.insight_id
    items = {
        e.tenant_id: stamp[e.entry_seq]
        for e in entries
        if isinstance(e, TenantItemEntry)
        and e.localized is not None
        and e.localized.insight_id == first
    }
    assert items["tribuna-austral"] - items["northlight-sport"] >= 0.5


def test_when_publishing_one_partner_s_item_fails_the_others_still_in_work_are_stopped() -> None:
    cancelled: dict[str, float] = {}
    refused: list[float] = []

    class Slow:
        provenance = Provenance(
            agent="localizer", prompt_version="v1.0", model="fast", produced_by="model"
        )

        async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
            try:
                await anyio.sleep(30)
            except BaseException:
                cancelled.setdefault(request.policy.tenant_id, time.monotonic())
                raise
            raise RuntimeError("never reached")

    class Refusing(FeedLog):
        async def publish(
            self,
            build: Callable[[int], FeedEntry],
            *,
            generation: int | None = None,
            guard: Callable[[tuple[FeedEntry, ...]], None] | None = None,
        ) -> FeedEntry:
            entry = await super().publish(build, generation=generation, guard=guard)
            if (
                isinstance(entry, TenantItemEntry)
                and entry.tenant_id == "northlight-sport"
                and entry.item_kind == "insight"
                and not refused
            ):
                refused.append(time.monotonic())
                raise RuntimeError("the feed refused the item")
            return entry

    partners = Partners(
        [
            Partner(policy=p.policy, blocked=partial(blocked_topics_in, policy=p.policy))
            for p in bundled_store().all()
        ],
        localizer=Slow(),
    )
    log = Refusing("m42")

    async def first_insight() -> None:
        with anyio.move_on_after(5):
            await replay(
                demo_store().record("m42"), log, template_only, sleep=no_wait, partners=partners
            )

    anyio.run(first_insight)

    # The Spanish and German drafts were stopped as the English item failed, not left to run.
    assert {"tribuna-austral", "rheinblick-sport"} <= set(cancelled)
    assert all(at - refused[0] < 1.0 for at in cancelled.values())
