"""Every verified insight, correction and score change reaches each partner as its own item: in
its language, labelled as its policy requires, held for an editor where it must be, and timed."""

from functools import cache, partial

import anyio

from fourth_official_contracts import (
    Moment,
    TenantItemEntry,
)
from fourth_official_explain import Explanation, explain
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

    assert {i.state for i in held} == {"pending_approval"}
    assert all(i.approval_required for i in held)
    assert {i.state for i in of("rheinblick-sport", "insight")} == {"on_air"}


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
