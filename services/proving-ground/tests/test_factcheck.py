"""A claim still on air at full time must agree with what finally happened."""

from functools import cache

from fourth_official_contracts import FailedClaim, GoalEvent, Insight, parse_insight
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


ITEM = "it-northlight-sport-in-m42-goal-HCY-s2044-a1-v1"


def check(aired: Insight) -> tuple[FailedClaim, ...]:
    return check_insight(aired, ITEM, m42())


def insight(event_id: str, *claims: str, headline: str = "A goal", kind: str = "goal") -> Insight:
    seq = goal(event_id).seq
    return parse_insight(
        {
            "insightId": f"in-m42-{kind}-HCY-s{seq:04d}-a1",
            "matchId": "m42",
            "momentId": f"mo-m42-{kind}-HCY-s{seq:04d}",
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

    assert check(insight(FIRST_GOAL, claim)) == ()


def test_a_claim_resting_on_a_goal_ruled_out_fails() -> None:
    (failure,) = check(insight(VOIDED_GOAL, "{{club:HCY}} score"))

    assert (failure.item_id, failure.claim_id) == (ITEM, "cl-1")
    assert failure.reasons == (f"rests on {VOIDED_GOAL}, which was ruled out",)


def test_the_var_decision_may_cite_the_goal_it_rules_out() -> None:
    assert (
        check(insight(VOIDED_GOAL, "VAR rules out the {{club:HCY}} goal", kind="var_overturn"))
        == ()
    )


def test_crediting_the_scorer_the_panel_replaced_fails() -> None:
    old = goal(REASSIGNED_GOAL).scorer_id
    (failure,) = check(insight(REASSIGNED_GOAL, f"{{{{player:{old}}}}} scores"))

    assert failure.reasons == (f"names {old}, who is not credited in its events",)


def test_a_minute_none_of_its_events_happened_in_fails() -> None:
    (failure,) = check(insight(FIRST_GOAL, "{{club:HCY}} score in {{minute:3}}"))

    assert failure.reasons == ("names minute 3, when none of its events happened",)


def test_a_score_that_counted_a_goal_later_ruled_out_fails() -> None:
    after = insight(VOIDED_GOAL, "{{club:HCY}} lead {{score}}")
    (failure,) = check(after)

    assert "states the score as 2-0; it was 1-0" in failure.reasons


def test_the_headline_is_held_to_the_same_truth() -> None:
    old = goal(REASSIGNED_GOAL).scorer_id
    checked = insight(REASSIGNED_GOAL, "{{club:HCY}} score", headline=f"{{{{player:{old}}}}}!")

    (failure,) = check(checked)
    assert failure.claim_id == "headline"
    assert failure.text == f"{{{{player:{old}}}}}!"
    assert failure.event_ids == (REASSIGNED_GOAL,)
