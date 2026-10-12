"""A claim still on air at full time must agree with what finally happened."""

from functools import cache

from fourth_official_contracts import GoalEvent, Insight, parse_insight
from fourth_official_proving.factcheck import check_insight
from fourth_official_proving.truth import Truth, truth_of
from fourth_official_simulator.demo import demo_matchday
from fourth_official_simulator.engine import play

VOIDED_GOAL = "m42-e1702"
REASSIGNED_GOAL = "m42-e2044"
FIRST_GOAL = "m42-e0287"


@cache
def m42() -> Truth:
    return truth_of(play(demo_matchday()[0]))


def goal(event_id: str) -> GoalEvent:
    event = m42().original[event_id]
    assert isinstance(event, GoalEvent)
    return event


def insight(event_id: str, *claims: str, headline: str = "A goal") -> Insight:
    seq = goal(event_id).seq
    return parse_insight(
        {
            "insightId": f"in-m42-goal-HCY-s{seq:04d}-a1",
            "matchId": "m42",
            "momentId": f"mo-m42-goal-HCY-s{seq:04d}",
            "asOfSeq": seq,
            "locale": "en",
            "headline": headline,
            "claims": [
                {
                    "claimId": f"cl-{n}",
                    "type": "milestone",
                    "text": text,
                    "evidence": {"eventIds": [event_id], "metricSnapshotIds": []},
                }
                for n, text in enumerate(claims, start=1)
            ],
            "provenance": {
                "agent": "analyst",
                "promptVersion": "v1.2",
                "model": "fast",
                "producedBy": "model",
            },
        }
    )


def test_a_true_claim_passes() -> None:
    first = goal(FIRST_GOAL)
    claim = f"{{{{player:{first.scorer_id}}}}} scores in minute {{{{minute:{first.clock.minute}}}}}"

    assert check_insight(insight(FIRST_GOAL, claim), m42()) == ()


def test_a_claim_resting_on_a_goal_ruled_out_fails() -> None:
    (failure,) = check_insight(insight(VOIDED_GOAL, "{{club:HCY}} score"), m42())

    assert failure.claim_id == "cl-1"
    assert failure.reasons == (f"rests on {VOIDED_GOAL}, which was ruled out",)


def test_crediting_the_scorer_the_panel_replaced_fails() -> None:
    old = goal(REASSIGNED_GOAL).scorer_id
    (failure,) = check_insight(insight(REASSIGNED_GOAL, f"{{{{player:{old}}}}} scores"), m42())

    assert failure.reasons == (f"names {old}, who is not credited in its events",)


def test_a_minute_none_of_its_events_happened_in_fails() -> None:
    (failure,) = check_insight(insight(FIRST_GOAL, "{{club:HCY}} score in {{minute:3}}"), m42())

    assert failure.reasons == ("names minute 3, when none of its events happened",)


def test_a_score_that_counted_a_goal_later_ruled_out_fails() -> None:
    after = insight(VOIDED_GOAL, "{{club:HCY}} lead {{score}}")
    (failure,) = check_insight(after, m42())

    assert "states the score as 2-0; it was 1-0" in failure.reasons


def test_the_headline_is_held_to_the_same_truth() -> None:
    old = goal(REASSIGNED_GOAL).scorer_id
    checked = insight(REASSIGNED_GOAL, "{{club:HCY}} score", headline=f"{{{{player:{old}}}}}!")

    (failure,) = check_insight(checked, m42())
    assert failure.claim_id == "headline"
    assert failure.text == f"{{{{player:{old}}}}}!"
    assert failure.event_ids == (REASSIGNED_GOAL,)
