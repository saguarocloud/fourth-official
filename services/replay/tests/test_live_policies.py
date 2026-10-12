"""A partner's policy changes mid-match and the next item follows it, with no restart."""

from functools import partial

import anyio

from fourth_official_contracts import Moment, MomentEntry, TenantItemEntry, TenantPolicy
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_policy import blocked_topics_in, bundled_store
from fourth_official_replay import FeedLog, ReplayConfig, replay
from fourth_official_replay.partners import Partner, Partners
from fourth_official_verifier import MatchFacts

NORTHLIGHT = "northlight-sport"
SECOND_HALF = 45


async def no_wait(seconds: float) -> None:
    return None


def test_a_policy_changed_mid_match_governs_the_next_item() -> None:
    policies: dict[str, TenantPolicy] = {
        loaded.policy.tenant_id: loaded.policy for loaded in bundled_store().all()
    }
    first_half = policies[NORTHLIGHT]
    # From the second half, Northlight wants an editor on every narrative item.
    second_half = first_half.model_copy(
        update={"version": first_half.version + 1, "approval_required": ("insight",)}
    )

    def source(tenant_id: str) -> Partner:
        policy = policies[tenant_id]
        return Partner(policy=policy, blocked=partial(blocked_topics_in, policy=policy))

    async def explainer(moment: Moment, facts: MatchFacts) -> Explanation:
        if moment.clock.minute >= SECOND_HALF:
            policies[NORTHLIGHT] = second_half
        return await explain(moment, facts, [])

    log = FeedLog("m42")
    anyio.run(
        lambda: replay(
            demo_store().record("m42"),
            log,
            explainer,
            config=ReplayConfig(),
            sleep=no_wait,
            partners=Partners(
                [source(tenant) for tenant in policies], localizer=None, source=source
            ),
        )
    )

    northlight = [
        e
        for e in log.entries
        if isinstance(e, TenantItemEntry)
        and e.tenant_id == NORTHLIGHT
        and e.item_kind == "insight"
        and e.overlay.supersedes is None
        and e.state in ("on_air", "pending_approval")
    ]
    # When the moment happened, not when its graphic aired (a fast replay airs them late).
    minute = {
        e.moment.moment_id: e.moment.clock.minute for e in log.entries if isinstance(e, MomentEntry)
    }

    def at(item: TenantItemEntry) -> int:
        assert item.localized is not None
        return minute[item.localized.moment_id]

    before = [e for e in northlight if at(e) < SECOND_HALF]
    after = [e for e in northlight if at(e) >= SECOND_HALF]
    assert before
    assert after
    assert {e.state for e in before} == {"on_air"}
    assert {e.state for e in after} == {"pending_approval"}
    assert all(e.approval_required for e in after)


def test_a_template_the_policy_no_longer_allows_is_not_aired() -> None:
    policies: dict[str, TenantPolicy] = {
        loaded.policy.tenant_id: loaded.policy for loaded in bundled_store().all()
    }
    plain = policies[NORTHLIGHT]
    policies[NORTHLIGHT] = plain.model_copy(
        update={"templates": tuple(t for t in plain.templates if t != "score_bug")}
    )

    def source(tenant_id: str) -> Partner:
        policy = policies[tenant_id]
        return Partner(policy=policy, blocked=partial(blocked_topics_in, policy=policy))

    async def explainer(moment: Moment, facts: MatchFacts) -> Explanation:
        return await explain(moment, facts, [])

    log = FeedLog("m42")
    anyio.run(
        lambda: replay(
            demo_store().record("m42"),
            log,
            explainer,
            config=ReplayConfig(),
            sleep=no_wait,
            partners=Partners(
                [source(tenant) for tenant in policies], localizer=None, source=source
            ),
        )
    )

    scores = [
        e.tenant_id
        for e in log.entries
        if isinstance(e, TenantItemEntry) and e.overlay.content.template == "score_bug"
    ]
    assert NORTHLIGHT not in scores
    assert "rheinblick-sport" in scores
