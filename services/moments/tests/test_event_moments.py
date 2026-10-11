"""Moments shown by single events: goals, big chances, sendings-off and VAR overturns."""

from events import penalty_awarded, shot
from fourth_official_contracts import MatchEvent, Moment, parse_moment
from fourth_official_moments.detector import DetectorState, detect
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import prepare
from moment_builders import card, foul, goal, var_check, var_decision

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")


def moments(*events: MatchEvent) -> tuple[Moment, ...]:
    _, found = detect(prepare(CTX, events))
    return found


def test_a_goal_is_a_moment_citing_the_shot_and_the_goal() -> None:
    (found,) = moments(
        shot(1, 12, "HCY", outcome="goal"), goal(2, 12, "HCY", shot_seq=1, home=1, away=0)
    )

    assert (found.kind, found.club, found.as_of_seq) == ("goal", "HCY", 2)
    assert found.event_ids == ("m42-e0001", "m42-e0002")
    assert found.clock.minute == 12
    assert parse_moment(found.to_wire()) == found


def test_a_big_chance_is_a_good_shot_that_did_not_go_in() -> None:
    found = moments(
        shot(1, 20, "NGT", at=(11.0, 34.0), outcome="saved"),  # 11 m out, central: 0.30 xG
        shot(2, 21, "NGT", at=(8.0, 34.0), outcome="off_target"),  # 8 m out: about 0.47 xG
        shot(3, 22, "NGT", at=(30.0, 34.0), outcome="saved"),  # 30 m out: a speculative effort
    )

    assert [(m.kind, m.club, m.event_ids) for m in found] == [
        ("big_chance", "NGT", ("m42-e0002",)),
    ]


def test_a_missed_penalty_is_a_big_chance_citing_the_award() -> None:
    (found,) = moments(penalty_awarded(1, 30, "HCY"), shot(2, 30, "HCY", outcome="saved"))

    assert (found.kind, found.event_ids) == ("big_chance", ("m42-e0001", "m42-e0002"))


def test_a_sending_off_is_a_moment_for_the_side_that_lost_a_player() -> None:
    found = moments(
        foul(1, 38, "NGT", "HCY"),
        card(2, 38, "NGT", kind="red", foul_seq=1),
        foul(3, 50, "HCY", "NGT"),
        card(4, 50, "HCY", kind="yellow", foul_seq=3),
        card(5, 70, "HCY", kind="second_yellow", foul_seq=None),
    )

    assert [(m.kind, m.club, m.event_ids) for m in found] == [
        ("red_card", "NGT", ("m42-e0001", "m42-e0002")),
        ("red_card", "HCY", ("m42-e0005",)),
    ]


def test_an_overturned_goal_is_a_moment_for_the_side_that_lost_it() -> None:
    found = moments(
        shot(1, 67, "HCY", outcome="goal"),
        goal(2, 67, "HCY", shot_seq=1, home=2, away=0),
        var_check(3, 67, target_seq=2),
        var_decision(4, 68, target_seq=2, overturned=True),
    )

    assert [(m.kind, m.club) for m in found] == [("goal", "HCY"), ("var_overturn", "HCY")]
    assert found[1].event_ids == ("m42-e0002", "m42-e0003", "m42-e0004")


def test_a_confirmed_goal_is_not_a_second_moment() -> None:
    found = moments(
        shot(1, 67, "HCY", outcome="goal"),
        goal(2, 67, "HCY", shot_seq=1, home=1, away=0),
        var_decision(3, 68, target_seq=2, overturned=False),
    )

    assert [m.kind for m in found] == ["goal"]


def test_detection_resumes_where_it_left_off() -> None:
    first = (shot(1, 12, "HCY", outcome="goal"), goal(2, 12, "HCY", shot_seq=1, home=1, away=0))
    later = (
        *first,
        shot(3, 20, "NGT", outcome="goal"),
        goal(4, 20, "NGT", shot_seq=3, home=1, away=1),
    )

    state, early = detect(prepare(CTX, first))
    state, rest = detect(prepare(CTX, later), state)

    assert [m.as_of_seq for m in early] == [2]
    assert [m.as_of_seq for m in rest] == [4]
    assert state.last_seq == 4
    assert detect(prepare(CTX, later))[1] == (*early, *rest)


def test_a_fresh_state_starts_from_the_first_event() -> None:
    assert DetectorState().last_seq == 0


def test_an_overturn_of_an_event_the_detector_never_saw_is_not_a_moment() -> None:
    assert moments(var_decision(5, 68, target_seq=2, overturned=True)) == ()
