"""The corrections desk: when the source data changes, it finds every partner item resting on the
corrected event and acts as each partner's policy says. A voided fact is pulled everywhere; an
amended one is regenerated from the corrected facts (auto-amend), pulled (retract-and-notify) or
regenerated and held for an editor (escalate). Nothing it does goes unreported."""

from datetime import UTC, datetime
from functools import partial

import anyio
import pytest

from fourth_official_contracts import (
    CorrectionAction,
    CorrectionReportEntry,
    EventAmended,
    EventVoided,
    FeedEntry,
    GoalEvent,
    MatchClock,
    TenantItemEntry,
    parse_feed_entry,
)
from fourth_official_match_data import demo_store
from fourth_official_policy import blocked_topics_in, bundled_store
from fourth_official_replay import FeedLog, ReplayConfig, replay
from fourth_official_replay.corrections import corrected_facts, report_entry, touched
from fourth_official_replay.partners import EntryBuilder, Partner, Partners
from fourth_official_replay.replay import facts_for
from test_partners import no_wait, template_only

AT = MatchClock(period=2, minute=91, second=0)
NOW = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)
RECORD = demo_store().record("m42")
_VOID, _AMEND = RECORD.corrections
assert isinstance(_VOID, EventVoided)
assert isinstance(_AMEND, EventAmended)
VOID: EventVoided = _VOID
AMEND: EventAmended = _AMEND


def entries() -> tuple[FeedEntry, ...]:
    log = FeedLog("m42")
    anyio.run(
        lambda: replay(
            RECORD, log, template_only, config=ReplayConfig(), sleep=no_wait, partners=partners()
        )
    )
    return log.entries


def partners(escalate: bool = False) -> Partners:
    chosen = []
    for loaded in bundled_store().all():
        policy = loaded.policy
        if escalate:
            policy = policy.model_copy(update={"correction_behaviour": "escalate"})
        chosen.append(Partner(policy=policy, blocked=partial(blocked_topics_in, policy=policy)))
    return Partners(chosen, localizer=None)


ENTRIES = entries()


def _by_the_desk(entry: FeedEntry) -> bool:
    if entry.kind == "correction_report":
        return True
    return isinstance(entry, TenantItemEntry) and (
        entry.state in ("retracted", "amended") or entry.overlay.supersedes is not None
    )


# The feed as published before the desk acted: what the desk's work is checked against.
BEFORE = tuple(e for e in ENTRIES if not _by_the_desk(e))


Corrected = tuple[list[EntryBuilder], list[CorrectionAction]]


def correct(correction: EventVoided | EventAmended, escalate: bool = False) -> Corrected:
    facts = corrected_facts(facts_for(RECORD), correction)

    async def run() -> Corrected:
        return await partners(escalate).correct(correction, BEFORE, facts, AT)

    return anyio.run(run)


def built(builders: list[EntryBuilder], start: int = 500) -> list[TenantItemEntry]:
    return [b(start + n) for n, b in enumerate(builders)]


def test_touched_finds_the_insights_resting_on_an_event_but_not_the_one_explaining_its_void() -> (
    None
):
    insight_ids, items = touched(BEFORE, VOID)

    kinds = {i.split("-")[2] for i in insight_ids}
    assert kinds == {"goal"}
    assert {i.tenant_id for i in items} == {
        "northlight-sport",
        "tribuna-austral",
        "rheinblick-sport",
    }
    assert {i.localized.insight_id for i in items if i.localized} <= set(insight_ids)


def test_a_voided_fact_is_pulled_from_every_partner() -> None:
    builders, actions = correct(VOID)

    assert {a.action for a in actions} == {"retracted"}
    assert {a.tenant_id for a in actions} == {
        "northlight-sport",
        "tribuna-austral",
        "rheinblick-sport",
    }
    assert {e.state for e in built(builders)} == {"retracted"}


def test_an_amended_fact_follows_each_partner_s_policy() -> None:
    builders, actions = correct(AMEND)

    by_partner = {a.tenant_id: a for a in actions}
    assert by_partner["northlight-sport"].action == "amended"
    assert by_partner["rheinblick-sport"].action == "amended"
    assert by_partner["tribuna-austral"].action == "retracted"
    made = built(builders)
    replaced = [e for e in made if e.state == "amended"]
    new = [e for e in made if e.overlay.supersedes is not None]
    assert len(replaced) == len(new) == 2
    for entry in new:
        assert entry.state == "on_air"
        assert entry.overlay.version == 2
        assert entry.overlay.in_at == AT
        assert entry.localized is not None
        assert entry.localized.version == 2
        assert parse_feed_entry(entry.to_wire()) == entry


def test_an_amended_item_names_the_corrected_scorer() -> None:
    builders, _ = correct(AMEND)
    new = next(
        e for e in built(builders) if e.tenant_id == "northlight-sport" and e.overlay.supersedes
    )
    assert AMEND.changes.scorer_id is not None
    scorer = RECORD.players[AMEND.changes.scorer_id].name

    assert entry_text(new).count(scorer) >= 1


def entry_text(entry: TenantItemEntry) -> str:
    assert entry.rendered is not None
    return " ".join((entry.rendered.headline, *entry.rendered.claims))


def test_escalation_holds_the_regenerated_version_for_an_editor() -> None:
    builders, actions = correct(AMEND, escalate=True)

    on_air = [a for a in actions if a.was == "on_air"]
    assert {a.action for a in on_air} == {"escalated"}
    held = [e for e in built(builders) if e.overlay.supersedes is not None]
    assert held
    assert {e.state for e in held} == {"pending_approval"}
    assert all(e.approval_required for e in held)


def test_items_already_off_air_are_left_alone() -> None:
    first = correct(VOID)[0]
    after = (*BEFORE, *built(first, start=len(ENTRIES) + 1))

    async def again() -> Corrected:
        facts = corrected_facts(facts_for(RECORD), VOID)
        return await partners().correct(VOID, after, facts, AT)

    builders, actions = anyio.run(again)
    assert (builders, actions) == ([], [])


def test_corrected_facts_amend_the_event_and_leave_a_void_to_the_voids() -> None:
    facts = facts_for(RECORD)

    amended = corrected_facts(facts, AMEND)
    goal = next(e for e in amended.match.events if e.event_id == AMEND.target_event_id)
    assert isinstance(goal, GoalEvent)
    assert goal.scorer_id == AMEND.changes.scorer_id
    assert corrected_facts(facts, VOID) is facts


def test_the_report_records_what_was_done_and_how_long_it_took() -> None:
    _, actions = correct(AMEND)
    insight_ids, _ = touched(BEFORE, AMEND)

    report = report_entry(AMEND, insight_ids, actions, started_at=NOW, elapsed_ms=12)(700)

    assert report.kind == "correction_report"
    assert report.correction_id == AMEND.correction_id
    assert report.elapsed_ms == 12
    assert len(report.actions) == len(actions)
    assert parse_feed_entry(report.to_wire()) == report


def test_a_policy_change_in_flight_is_not_needed_to_retract_a_held_item() -> None:
    _, actions = correct(AMEND, escalate=True)

    held = [a for a in actions if a.was == "pending_approval"]
    assert held
    assert {a.action for a in held} == {"retracted"}


@pytest.mark.parametrize("correction", [VOID, AMEND])
def test_every_action_is_a_partner_item_on_the_feed(correction: EventVoided | EventAmended) -> None:
    _, actions = correct(correction)
    ids = {e.overlay.item_id for e in BEFORE if isinstance(e, TenantItemEntry)}

    assert actions
    assert all(a.item_id in ids for a in actions)


# --- In the replay -------------------------------------------------------------------------------


def test_the_replay_corrects_everything_published_and_reports_it_once_per_finding() -> None:
    reports = [e for e in ENTRIES if isinstance(e, CorrectionReportEntry)]
    acted = {(r.correction_id, a.tenant_id, a.insight_id) for r in reports for a in r.actions}

    assert {r.correction_id for r in reports} == {VOID.correction_id, AMEND.correction_id}
    assert len(acted) == sum(len(r.actions) for r in reports)
    assert {(c, t) for c, t, _ in acted} == {
        (c.correction_id, t)
        for c in (VOID, AMEND)
        for t in ("northlight-sport", "tribuna-austral", "rheinblick-sport")
    }


def test_after_the_replay_no_item_rests_on_a_voided_fact_or_an_old_scorer() -> None:
    latest: dict[str, TenantItemEntry] = {}
    for entry in ENTRIES:
        if isinstance(entry, TenantItemEntry) and entry.localized is not None:
            latest[entry.overlay.item_id] = entry
    live = [e for e in latest.values() if e.state in ("on_air", "pending_approval")]
    for item in live:
        assert item.localized is not None
        evidence = {x for c in item.localized.claims for x in c.evidence.event_ids}
        if VOID.target_event_id in evidence:
            assert "var" in item.localized.insight_id
        if AMEND.target_event_id in evidence:
            assert item.overlay.version == 2
