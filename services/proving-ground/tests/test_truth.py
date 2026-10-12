"""What really happened: the simulator's own events with every later correction applied."""

from functools import cache

from fourth_official_contracts import GoalEvent, ShotEvent
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

    assert m42().score_at(after_void, corrected=False) == (2, 0)
    assert m42().score_at(after_void) == (1, 0)


def test_the_final_score_is_the_ground_truths() -> None:
    final = play(demo_matchday()[0]).ground_truth.final_score

    assert m42().score_at(10**9) == (final.home, final.away)
