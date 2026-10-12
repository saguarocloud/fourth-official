"""What really happened: the simulator's own events with every later correction applied."""

from dataclasses import replace
from functools import cache

from fourth_official_contracts import EventAmended, GoalEvent, ShotEvent
from fourth_official_proving.truth import Truth, truth_of
from fourth_official_simulator.demo import demo_matchday
from fourth_official_simulator.engine import play

# m42: HCY's goal at 67' is ruled out by VAR (c-m42-01); HCY's 89' goal is credited to another
# player after the final whistle (c-m42-02).
VOIDED_GOAL = "m42-e1702"
REASSIGNED_GOAL = "m42-e2044"


@cache
def m42() -> Truth:
    return truth_of(play(demo_matchday()[0]))


def goal(event_id: str) -> GoalEvent:
    found = play(demo_matchday()[0]).events
    event = next(e for e in found if e.event_id == event_id)
    assert isinstance(event, GoalEvent)
    return event


def test_a_goal_ruled_out_is_void() -> None:
    assert VOIDED_GOAL in m42().voided
    assert REASSIGNED_GOAL not in m42().voided


def test_a_reassigned_goal_names_its_new_scorer_and_no_longer_its_old_one() -> None:
    original = goal(REASSIGNED_GOAL)
    involved = m42().participants([REASSIGNED_GOAL])

    assert original.scorer_id not in involved
    assert len(involved - {original.assist_id}) == 1


def test_the_shot_behind_a_cited_goal_does_not_vouch_for_the_old_scorer() -> None:
    shot = next(
        e.event_id
        for e in play(demo_matchday()[0]).events
        if isinstance(e, ShotEvent)
        and e.event_id < REASSIGNED_GOAL
        and e.outcome == "goal"
        and e.clock.minute >= 88
    )

    assert goal(REASSIGNED_GOAL).scorer_id not in m42().participants([shot, REASSIGNED_GOAL])


def test_minutes_are_those_of_the_cited_events() -> None:
    assert m42().minutes([REASSIGNED_GOAL]) == {goal(REASSIGNED_GOAL).clock.minute}


def test_the_score_leaves_out_goals_ruled_out() -> None:
    after_void = goal(VOIDED_GOAL).seq + 1

    assert m42().score_at(after_void, as_published=True) == (2, 0)
    assert m42().score_at(after_void) == (1, 0)


def test_the_score_as_published_drops_a_goal_once_var_has_ruled_it_out() -> None:
    decided = m42().voided_at[VOIDED_GOAL]

    assert decided > goal(VOIDED_GOAL).seq
    assert m42().score_at(decided, as_published=True) == (1, 0)


def test_the_final_score_is_the_ground_truths() -> None:
    final = play(demo_matchday()[0]).ground_truth.final_score

    assert m42().score_at(10**9) == (final.home, final.away)


def amended(**changes: object) -> Truth:
    """m42 with one more correction: the 89' goal amended as given."""
    played = play(demo_matchday()[0])
    extra = EventAmended.model_validate(
        {
            "correctionId": "c-m42-09",
            "matchId": "m42",
            "reason": "ACCREDITATION_PANEL",
            "issuedAt": "2026-10-24T16:30:00Z",
            "targetEventId": REASSIGNED_GOAL,
            "newVersion": 3,
            "kind": "EVENT_AMENDED",
            "changes": changes,
        }
    )
    return truth_of(replace(played, corrections=(*played.corrections, extra)))


def test_an_assist_the_panel_removes_is_no_longer_credited() -> None:
    assist = goal(REASSIGNED_GOAL).assist_id
    assert assist is not None

    assert assist not in amended(assistId=None).participants([REASSIGNED_GOAL])


def test_a_goal_moved_to_another_minute_is_read_at_that_minute() -> None:
    clock = {"period": 2, "minute": 87, "second": 5}

    assert amended(clock=clock).minutes([REASSIGNED_GOAL]) == {87}


def test_a_goal_made_an_own_goal_counts_for_the_other_side() -> None:
    final = m42().score_at(10**9)
    defender = "NGT-04"

    turned = amended(scorerId=defender, ownGoal=True, assistId=None)
    assert turned.score_at(10**9) == (final[0], final[1])
    assert turned.participants([REASSIGNED_GOAL]) == {defender}
