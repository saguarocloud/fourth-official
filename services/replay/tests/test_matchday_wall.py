"""The Control Room's wall, computed from each match's feed: score, clock, who is on air, what
awaits an editor, corrections, the latest items and the latest correction."""

from functools import cache

import anyio

from fourth_official_contracts import (
    ClockEntry,
    CorrectionEntry,
    CorrectionReportEntry,
    TenantItemEntry,
)
from fourth_official_match_data import demo_store
from fourth_official_replay import FeedLog, fixed_clocks, replay
from fourth_official_replay.wall import Played, played_from, wall
from test_partners import no_wait, partners, template_only


@cache
def finished() -> FeedLog:
    log = FeedLog("m42")

    async def play() -> None:
        await log.reset()
        await replay(
            demo_store().record("m42"),
            log,
            template_only,
            sleep=no_wait,
            partners=partners(),
            clocks=fixed_clocks(),
        )

    anyio.run(play)
    return log


def m42(state: str = "finished", log: FeedLog | None = None) -> Played:
    return played_from(demo_store().record("m42"), state, log or finished())  # type: ignore[arg-type]


def test_a_match_not_started_shows_nil_nil_and_no_clock() -> None:
    match = wall([m42("idle", FeedLog("m42"))], generated_at=fixed_clocks().wall()).matches[0]

    assert (match.home, match.away) == ("HCY", "NGT")
    assert (match.score.home, match.score.away, match.clock) == (0, 0, None)
    assert (match.items, match.pending_approvals, match.corrections, match.on_air) == (0, 0, 0, ())


def test_a_match_shows_its_score_and_clock_as_last_published() -> None:
    entries = finished().entries
    last = [e for e in entries if isinstance(e, ClockEntry)][-1]

    match = wall([m42()], generated_at=fixed_clocks().wall()).matches[0]

    assert match.score == last.score
    assert match.clock == last.clock
    assert match.corrections == sum(isinstance(e, CorrectionEntry) for e in entries)


def test_items_are_first_versions_and_pending_ones_still_await_an_editor() -> None:
    entries = finished().entries
    latest: dict[str, TenantItemEntry] = {}
    for e in entries:
        if isinstance(e, TenantItemEntry) and e.localized is not None:
            latest[e.overlay.item_id] = e
    firsts = [e for e in latest.values() if e.localized and e.localized.version == 1]

    match = wall([m42()], generated_at=fixed_clocks().wall()).matches[0]

    assert match.items == len(firsts)
    assert match.pending_approvals == sum(e.state == "pending_approval" for e in latest.values())
    assert match.pending_approvals > 0


def test_activity_is_the_latest_narrative_items_newest_first_as_the_audience_reads_them() -> None:
    result = wall([m42()], generated_at=fixed_clocks().wall(), activity_limit=5)

    assert len(result.activity) == 5
    seqs = [a.entry_seq for a in result.activity]
    assert seqs == sorted(seqs, reverse=True)
    by_seq = {e.entry_seq: e for e in finished().entries}
    for item in result.activity:
        entry = by_seq[item.entry_seq]
        assert isinstance(entry, TenantItemEntry)
        assert entry.rendered is not None
        assert item.headline == entry.rendered.headline
        assert entry.localized is not None
        assert item.ai_written is (entry.localized.provenance.produced_by == "model")
    # Templates only in this replay: nothing a model wrote.
    assert not any(a.ai_written for a in result.activity)


def test_the_latest_correction_carries_what_the_desk_did() -> None:
    entries = finished().entries
    correction = [e for e in entries if isinstance(e, CorrectionEntry)][-1]
    reports = [
        e
        for e in entries
        if isinstance(e, CorrectionReportEntry)
        and e.correction_id == correction.correction.correction_id
    ]
    actions = [a for r in reports for a in r.actions]

    latest = wall([m42()], generated_at=fixed_clocks().wall()).latest_correction

    assert latest is not None
    assert latest.correction_id == correction.correction.correction_id
    assert (latest.out_text, latest.in_text, latest.summary) == (
        correction.out_text,
        correction.in_text,
        correction.summary,
    )
    assert latest.items_corrected == len(actions) > 0
    assert latest.partners == len({a.tenant_id for a in actions})
    assert latest.languages == len({a.locale for a in actions})
    assert latest.elapsed_ms == reports[0].elapsed_ms
    assert latest.event_clock is not None


def test_a_partner_is_on_air_while_one_of_its_graphics_covers_the_clock() -> None:
    match = wall([m42()], generated_at=fixed_clocks().wall()).matches[0]

    assert match.clock is not None
    clock = match.clock
    latest: dict[str, TenantItemEntry] = {}
    for e in finished().entries:
        if isinstance(e, TenantItemEntry):
            latest[e.overlay.item_id] = e
    covering = {
        e.tenant_id
        for e in latest.values()
        if e.state == "on_air"
        and e.item_kind != "score"
        and e.overlay.in_at.period == clock.period
        and (e.overlay.in_at.minute, e.overlay.in_at.second)
        <= (clock.minute, clock.second)
        < (e.overlay.out_at.minute, e.overlay.out_at.second)
    }
    assert set(match.on_air) == covering


def test_mid_match_the_partners_with_a_lower_third_up_are_lit_and_a_score_bug_alone_is_not() -> (
    None
):
    log = finished()
    entries, timing = log.snapshot()
    aired = next(
        i
        for i, e in enumerate(entries)
        if isinstance(e, TenantItemEntry) and e.state == "on_air" and e.item_kind == "insight"
    )
    # The feed as it stood just after that lower third went out, with a clock entry at its time.
    item = entries[aired]
    assert isinstance(item, TenantItemEntry)
    clock = ClockEntry(
        kind="clock",
        entry_seq=aired + 2,
        match_id="m42",
        as_of_seq=1,
        clock=item.overlay.in_at,
        score=[e for e in entries[:aired] if isinstance(e, ClockEntry)][-1].score,
    )
    so_far = Played(
        match_id="m42",
        home="HCY",
        away="NGT",
        state="running",
        entries=(*entries[: aired + 1], clock),
        timing=type(timing)(timing.started, (*timing.published[: aired + 1], 0.0), timing.played),
        event_clocks={},
    )

    match = wall([so_far], generated_at=fixed_clocks().wall()).matches[0]

    assert item.tenant_id in match.on_air
