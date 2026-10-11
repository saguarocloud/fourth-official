"""Match Data tools: read-only facts about a match, never beyond what has been published."""

from functools import cache

import pytest

from fourth_official_contracts import parse_match_event, parse_metric_snapshot, parse_moment
from fourth_official_match_data import MatchDataError, demo_store, tools
from fourth_official_match_data.store import InMemoryStore


@cache
def store() -> InMemoryStore:
    return demo_store()


def featured_goal_seq() -> int:
    record = store().record("m42")
    return next(m.as_of_seq for m in record.moments if m.kind == "goal")


def test_matches_are_listed_with_their_clubs_and_progress() -> None:
    listed = tools.list_matches(store())

    assert [(m["matchId"], m["home"], m["away"]) for m in listed] == [
        ("m42", "HCY", "NGT"),
        ("m43", "KBA", "ASV"),
        ("m44", "CAL", "WMR"),
    ]
    assert listed[0]["homeName"] == "Harbour City"


def test_match_state_gives_the_score_and_clock_at_a_moment() -> None:
    seq = featured_goal_seq()

    before = tools.get_match_state(store(), "m42", as_of_seq=seq - 1)
    after = tools.get_match_state(store(), "m42", as_of_seq=seq)

    assert before["score"] == {"home": 0, "away": 0}
    assert after["score"] == {"home": 1, "away": 0}
    assert after["clock"]["minute"] == 12


def test_a_voided_goal_leaves_the_score_once_the_correction_is_issued() -> None:
    record = store().record("m42")
    overturn = next(m for m in record.moments if m.kind == "var_overturn")

    at_decision = tools.get_match_state(store(), "m42", as_of_seq=overturn.as_of_seq)
    final = tools.get_match_state(store(), "m42")

    assert at_decision["score"] == {"home": 1, "away": 0}
    assert final["score"] == {"home": 2, "away": 1}
    assert final["voidedEventIds"] == [overturn.event_ids[0]]


def test_metrics_are_snapshots_with_evidence() -> None:
    seq = featured_goal_seq()
    raw = tools.get_metric(
        store(), "m42", metric="possession", scope="HCY", window="match", as_of_seq=seq
    )

    snapshot = parse_metric_snapshot(raw)
    assert snapshot.as_of_seq == seq
    assert snapshot.inputs


def test_comparing_windows_gives_the_current_spell_and_the_one_before() -> None:
    compared = tools.compare_windows(
        store(), "m42", metric="pressing_intensity", scope="NGT", as_of_seq=1900
    )

    current, baseline = (
        parse_metric_snapshot(compared["current"]),
        parse_metric_snapshot(compared["baseline"]),
    )
    assert (current.window, baseline.window) == ("5m", "15m")
    assert baseline.as_of_seq < current.as_of_seq


def test_events_come_back_in_order_capped_and_filtered() -> None:
    events = tools.get_events(store(), "m42", from_seq=1, to_seq=500, types=["SHOT", "GOAL"])

    parsed = [parse_match_event(e) for e in events]
    assert {e.type for e in parsed} <= {"SHOT", "GOAL"}
    assert [e.seq for e in parsed] == sorted(e.seq for e in parsed)
    assert len(tools.get_events(store(), "m42", from_seq=1, to_seq=2000)) == tools.MAX_EVENTS


def test_players_are_looked_up_by_id_within_the_match() -> None:
    player = tools.get_player(store(), "m42", player_id="HCY-01")

    assert player["club"] == "HCY"
    assert player["position"] == "goalkeeper"
    with pytest.raises(MatchDataError, match="not in m42"):
        tools.get_player(store(), "m42", player_id="KBA-01")


def test_moments_are_listed_up_to_the_moment_asked_about() -> None:
    seq = featured_goal_seq()

    moments = [parse_moment(m) for m in tools.list_moments(store(), "m42", as_of_seq=seq)]

    assert [m.kind for m in moments] == ["goal"]


def test_nothing_after_the_live_position_is_ever_returned() -> None:
    live = store().with_live_seq("m42", featured_goal_seq())

    with pytest.raises(MatchDataError, match="not been published"):
        tools.get_match_state(live, "m42", as_of_seq=featured_goal_seq() + 1)
    assert tools.get_match_state(live, "m42")["asOfSeq"] == featured_goal_seq()
    assert (
        max(e["seq"] for e in tools.get_events(live, "m42", from_seq=1, to_seq=5000))
        <= featured_goal_seq()
    )
    assert all(m["asOfSeq"] <= featured_goal_seq() for m in tools.list_moments(live, "m42"))


def test_an_unknown_match_is_refused() -> None:
    with pytest.raises(MatchDataError, match="unknown match"):
        tools.get_match_state(store(), "m99")


def test_a_club_not_in_the_match_is_refused() -> None:
    with pytest.raises(MatchDataError, match="SLT"):
        tools.get_metric(store(), "m42", metric="xg", scope="SLT", window="5m")


def test_asking_beyond_the_live_position_is_refused_the_same_way_however_far() -> None:
    live = store().with_live_seq("m42", 100)
    for seq in (101, 10**6):
        with pytest.raises(MatchDataError, match="not been published"):
            tools.get_match_state(live, "m42", as_of_seq=seq)


def test_ranges_and_timing_are_checked() -> None:
    with pytest.raises(MatchDataError, match="from_seq"):
        tools.get_events(store(), "m42", from_seq=10, to_seq=5)
    with pytest.raises(MatchDataError, match="too early"):
        tools.compare_windows(store(), "m42", metric="xg", scope="HCY", as_of_seq=3)
    with pytest.raises(MatchDataError, match="no event"):
        tools.get_match_state(store().with_live_seq("m42", 0), "m42")


def test_a_metric_that_needs_the_match_scope_is_refused_politely() -> None:
    with pytest.raises(MatchDataError, match="match-wide"):
        tools.get_metric(store(), "m42", metric="control_chaos", scope="HCY", window="5m")
