"""Explain a moment: draft, verify, retry with feedback, fall back, and record every attempt."""

import asyncio
from dataclasses import dataclass, field

import anyio
import pytest

from explain_fixtures import featured, moment
from fourth_official_contracts import GoalEvent, Moment, Provenance
from fourth_official_explain.drafts import ClaimDraft, InsightDraft
from fourth_official_explain.pipeline import DraftRequest, Explanation, explain

FAST = Provenance(agent="analyst", prompt_version="v1.0", model="fast", produced_by="model")
QUALITY = Provenance(agent="analyst", prompt_version="v1.0", model="quality", produced_by="model")


def good_draft(subject: Moment) -> InsightDraft:
    facts, _ = featured()
    goal = facts.match.by_seq[subject.as_of_seq]
    assert isinstance(goal, GoalEvent)
    return InsightDraft(
        headline=f"{{{{club:{goal.team_id}}}}} take the lead",
        claims=[
            ClaimDraft(
                type="stat",
                text=f"{{{{player:{goal.scorer_id}}}}} scores for {{{{club:{goal.team_id}}}}} "
                f"in the {{{{minute:{goal.clock.minute}}}}}: {{{{score}}}}.",
                event_ids=list(subject.event_ids),
                snapshot_ids=[],
            )
        ],
    )


def with_text(draft: InsightDraft, text: str) -> InsightDraft:
    claim = draft.claims[0].model_copy(update={"text": text})
    return draft.model_copy(update={"claims": [claim]})


@dataclass
class Scripted:
    """A drafter that answers from a script and remembers what it was asked."""

    provenance: Provenance
    answers: list[InsightDraft | Exception]
    requests: list[DraftRequest] = field(default_factory=list)

    async def draft(self, request: DraftRequest) -> InsightDraft:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def run(subject: Moment, *drafters: Scripted, timeout: float = 20.0) -> Explanation:
    facts, _ = featured()
    return anyio.run(lambda: explain(subject, facts, drafters, timeout=timeout))


def test_a_draft_that_passes_is_published_as_written() -> None:
    goal = moment("goal")
    drafter = Scripted(FAST, [good_draft(goal)])

    result = run(goal, drafter)

    assert result.insight is not None
    assert result.verdict.passed
    assert result.insight.provenance == FAST
    assert result.insight.insight_id.endswith("-a1")
    assert [(a.model, a.outcome) for a in result.attempts] == [("fast", "passed")]


def test_a_failed_draft_is_retried_with_the_findings_as_feedback() -> None:
    goal = moment("goal")
    bad = with_text(good_draft(goal), "{{club:HCY}} have had 3 shots.")
    drafter = Scripted(FAST, [bad, good_draft(goal)])

    result = run(goal, drafter)

    assert [a.outcome for a in result.attempts] == ["failed", "passed"]
    assert drafter.requests[0].feedback == ()
    assert [f.code for f in drafter.requests[1].feedback] == ["BARE_NUMBER"]
    assert result.insight is not None
    assert result.insight.insight_id.endswith("-a2")


def test_a_retry_carries_the_draft_it_fixes_and_a_new_model_starts_fresh() -> None:
    goal = moment("goal")
    bad = with_text(good_draft(goal), "{{club:HCY}} have had 3 shots.")
    worse = with_text(good_draft(goal), "{{club:HCY}} have had 4 shots.")
    first = Scripted(FAST, [bad, worse, worse])
    second = Scripted(QUALITY, [good_draft(goal)])

    run(goal, first, second)

    assert [r.previous for r in first.requests] == [None, bad, worse]
    assert second.requests[0].previous is None


def test_after_its_retries_the_next_model_is_tried() -> None:
    goal = moment("goal")
    bad = with_text(good_draft(goal), "{{club:HCY}} have had 3 shots.")
    fast = Scripted(FAST, [bad, bad, bad])
    quality = Scripted(QUALITY, [good_draft(goal)])

    result = run(goal, fast, quality)

    assert [(a.model, a.outcome) for a in result.attempts] == [
        ("fast", "failed"),
        ("fast", "failed"),
        ("fast", "failed"),
        ("quality", "passed"),
    ]
    assert result.insight is not None
    assert result.insight.provenance == QUALITY


def test_when_every_model_fails_the_template_is_published() -> None:
    goal = moment("goal")
    bad = with_text(good_draft(goal), "{{club:HCY}} have had 3 shots.")

    result = run(goal, Scripted(FAST, [bad] * 3), Scripted(QUALITY, [bad] * 3))

    assert result.insight is not None
    assert result.insight.provenance.produced_by == "template"
    assert result.verdict.passed
    assert [a.model for a in result.attempts][-1] == "none"
    assert len(result.attempts) == 7


def test_a_draft_that_breaks_the_contract_is_a_failed_attempt_with_feedback() -> None:
    goal = moment("goal")
    malformed = with_text(good_draft(goal), "{{player:Smith}} scores.")
    drafter = Scripted(FAST, [malformed, good_draft(goal)])

    result = run(goal, drafter)

    assert [a.outcome for a in result.attempts] == ["failed", "passed"]
    assert [f.code for f in drafter.requests[1].feedback] == ["MALFORMED_INSIGHT"]
    assert "Smith" not in drafter.requests[1].feedback[0].detail
    assert "markup" in drafter.requests[1].feedback[0].detail


def test_a_model_error_moves_on_to_the_next_model_without_retrying() -> None:
    goal = moment("goal")
    broken = Scripted(FAST, [RuntimeError("service unavailable")])
    quality = Scripted(QUALITY, [good_draft(goal)])

    result = run(goal, broken, quality)

    assert [(a.model, a.outcome) for a in result.attempts] == [
        ("fast", "error"),
        ("quality", "passed"),
    ]


def test_a_slow_model_times_out_and_counts_as_an_error() -> None:
    goal = moment("goal")

    @dataclass
    class Slow(Scripted):
        async def draft(self, request: DraftRequest) -> InsightDraft:
            await asyncio.sleep(5)
            return await super().draft(request)

    result = run(goal, Slow(FAST, []), Scripted(QUALITY, [good_draft(goal)]), timeout=0.05)

    assert [(a.model, a.outcome) for a in result.attempts] == [
        ("fast", "error"),
        ("quality", "passed"),
    ]


def test_the_request_carries_the_moment_and_the_attempt() -> None:
    goal = moment("goal")
    drafter = Scripted(FAST, [good_draft(goal)])

    run(goal, drafter)

    assert drafter.requests[0].moment == goal
    assert drafter.requests[0].attempt == 1


@pytest.mark.parametrize("kind", ["goal", "big_chance", "var_overturn", "pressing_collapse"])
def test_with_no_model_at_all_every_moment_still_gets_a_verified_insight(kind: str) -> None:
    result = run(moment(kind))

    assert result.insight is not None
    assert result.verdict.passed


def test_a_bug_in_a_drafter_surfaces_instead_of_hiding_behind_the_template() -> None:
    goal = moment("goal")

    with pytest.raises(AttributeError):
        run(goal, Scripted(FAST, [AttributeError("bug")]))


def test_model_failures_are_logged_with_their_cause(caplog: pytest.LogCaptureFixture) -> None:
    goal = moment("goal")

    run(goal, Scripted(FAST, [RuntimeError("service unavailable")]))

    assert any("failed on attempt 1" in r.getMessage() and r.exc_info for r in caplog.records)


def test_more_attempts_than_insight_ids_can_number_are_refused() -> None:
    goal = moment("goal")
    facts, _ = featured()
    many = [Scripted(FAST, []) for _ in range(34)]

    with pytest.raises(ValueError, match="model attempts"):
        anyio.run(lambda: explain(goal, facts, many))
