"""Match Data tools: read-only facts about a match, never beyond what has been published."""

from dataclasses import replace
from datetime import timedelta
from functools import cache

import pytest

from fourth_official_contracts import EventVoided, GoalEvent, VarDecisionEvent
from fourth_official_match_data import MatchDataError, demo_store, tools
from fourth_official_match_data.store import InMemoryStore


@cache
def store() -> InMemoryStore:
    return demo_store()


def featured_goal_seq() -> int:
    record = store().record("m42")
    return next(m.as_of_seq for m in record.moments if m.kind == "goal")


def test_matches_are_listed_with_their_clubs_and_progress() -> None:
    listed = tools.list_matches(store()).matches

    assert [(m.match_id, m.home, m.away) for m in listed] == [
        ("m42", "HCY", "NGT"),
        ("m43", "KBA", "ASV"),
        ("m44", "CAL", "WMR"),
    ]
    assert listed[0].home_name == "Harbour City"


def test_a_match_not_yet_started_is_listed_without_a_clock() -> None:
    listed = tools.list_matches(store().with_live_seq("m43", 0)).matches

    assert (listed[1].live_seq, listed[1].clock) == (0, None)
    assert listed[0].clock is not None


def test_match_state_gives_the_score_and_clock_at_a_moment() -> None:
    seq = featured_goal_seq()

    before = tools.get_match_state(store(), "m42", as_of_seq=seq - 1)
    after = tools.get_match_state(store(), "m42", as_of_seq=seq)

    assert (before.score.home, before.score.away) == (0, 0)
    assert (after.score.home, after.score.away) == (1, 0)
    assert after.clock.minute == 12


def test_a_voided_goal_leaves_the_score_from_the_var_decision_on() -> None:
    record = store().record("m42")
    decision = next(e for e in record.match.events if isinstance(e, VarDecisionEvent))

    just_before = tools.get_match_state(store(), "m42", as_of_seq=decision.seq - 1)
    at_decision = tools.get_match_state(store(), "m42", as_of_seq=decision.seq)

    assert (just_before.score.home, just_before.score.away) == (2, 0)
    assert (at_decision.score.home, at_decision.score.away) == (1, 0)
    assert at_decision.voided_event_ids == (decision.target_event_id,)
    assert just_before.voided_event_ids == ()


def test_metrics_are_snapshots_with_evidence() -> None:
    seq = featured_goal_seq()
    snap = tools.get_metric(
        store(), "m42", metric="possession", scope="HCY", window="match", as_of_seq=seq
    )

    assert snap.as_of_seq == seq
    assert snap.inputs


def test_comparing_windows_gives_the_current_spell_and_the_one_before() -> None:
    compared = tools.compare_windows(
        store(), "m42", metric="pressing_intensity", scope="NGT", as_of_seq=1900
    )

    assert (compared.current.window, compared.baseline.window) == ("5m", "15m")
    assert compared.baseline.as_of_seq < compared.current.as_of_seq


def test_events_come_back_in_order_filtered_and_in_pages() -> None:
    shots = tools.get_events(store(), "m42", from_seq=1, to_seq=500, types=["SHOT", "GOAL"])
    first = tools.get_events(store(), "m42", from_seq=1, to_seq=2000)
    second = tools.get_events(store(), "m42", from_seq=first.next_seq or 0, to_seq=2000)

    assert {e.type for e in shots.events} <= {"SHOT", "GOAL"}
    assert shots.next_seq is None
    assert len(first.events) == tools.MAX_EVENTS
    assert first.next_seq == first.events[-1].seq + 1
    assert second.events[0].seq == first.next_seq


def test_players_are_looked_up_by_id_within_the_match() -> None:
    player = tools.get_player(store(), "m42", player_id="HCY-01")

    assert (player.club, player.position) == ("HCY", "goalkeeper")
    with pytest.raises(MatchDataError, match="not in this match"):
        tools.get_player(store(), "m42", player_id="KBA-01")


def test_moments_are_listed_up_to_the_moment_asked_about() -> None:
    moments = tools.list_moments(store(), "m42", as_of_seq=featured_goal_seq()).moments

    assert [m.kind for m in moments] == ["goal"]


def test_nothing_after_the_live_position_is_ever_returned() -> None:
    live = store().with_live_seq("m42", featured_goal_seq())
    seq = featured_goal_seq()

    assert tools.get_match_state(live, "m42").as_of_seq == seq
    assert max(e.seq for e in tools.get_events(live, "m42", from_seq=1, to_seq=5000).events) <= seq
    assert all(m.as_of_seq <= seq for m in tools.list_moments(live, "m42").moments)
    assert tools.get_metric(live, "m42", metric="xg", scope="HCY", window="match").as_of_seq == seq
    compared = tools.compare_windows(live, "m42", metric="xg", scope="HCY")
    assert compared.current.as_of_seq == seq


@pytest.mark.parametrize(
    "call",
    [
        lambda s: tools.get_match_state(s, "m42", as_of_seq=101),
        lambda s: tools.get_match_state(s, "m42", as_of_seq=10**6),
        lambda s: tools.get_metric(s, "m42", metric="xg", scope="HCY", window="5m", as_of_seq=101),
        lambda s: tools.compare_windows(s, "m42", metric="xg", scope="HCY", as_of_seq=999),
        lambda s: tools.list_moments(s, "m42", as_of_seq=500),
        lambda s: tools.get_events(s, "m42", from_seq=101, to_seq=200),
    ],
)
def test_asking_beyond_the_live_position_is_refused_the_same_way_however_far(call: object) -> None:
    live = store().with_live_seq("m42", 100)

    with pytest.raises(
        MatchDataError, match=r"^that point of the match has not been published yet$"
    ):
        call(live)  # type: ignore[operator]


def test_refusals_never_repeat_the_input() -> None:
    for call in (
        lambda: tools.get_match_state(store(), "m99"),
        lambda: tools.get_metric(store(), "m42", metric="xg", scope="SLT", window="5m"),
        lambda: tools.get_player(store(), "m42", player_id="ZZZ-99"),
        lambda: tools.get_metric(store(), "m42", metric="control_chaos", scope="HCY", window="5m"),
    ):
        with pytest.raises(MatchDataError) as refused:
            call()
        assert not any(echo in str(refused.value) for echo in ("m99", "SLT", "ZZZ", "HCY"))


def test_ranges_timing_and_the_live_position_are_checked() -> None:
    with pytest.raises(MatchDataError, match="from_seq"):
        tools.get_events(store(), "m42", from_seq=10, to_seq=5)
    with pytest.raises(MatchDataError, match="too early"):
        tools.compare_windows(store(), "m42", metric="xg", scope="HCY", as_of_seq=3)
    with pytest.raises(MatchDataError, match="no event"):
        tools.get_match_state(store().with_live_seq("m42", 0), "m42")
    with pytest.raises(MatchDataError, match="within the match"):
        store().with_live_seq("m42", 10**9)


def test_goals_in_the_store_are_the_simulated_goals() -> None:
    record = store().record("m42")

    assert sum(isinstance(e, GoalEvent) for e in record.match.events) == 4


def test_a_void_issued_after_the_last_event_is_not_yet_in_force() -> None:
    record = store().record("m42")
    goal = next(e for e in record.match.events if isinstance(e, GoalEvent))
    late = EventVoided(
        correction_id="c-m42-09",
        match_id="m42",
        reason="PROVIDER_RESTATEMENT",
        issued_at=record.match.events[-1].wall_clock + timedelta(hours=1),
        target_event_id=goal.event_id,
        new_version=2,
        kind="EVENT_VOIDED",
    )

    assert goal.event_id not in replace(record, corrections=(late,)).void_seqs()
