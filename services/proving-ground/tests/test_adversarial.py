"""Planted lies: deliberately wrong versions of real insights, which the Verifier must refuse."""

import asyncio
from collections import Counter
from functools import cache

from fourth_official_explain import Explanation, explain
from fourth_official_proving.adversarial import MUTATIONS, planted_lies, verifier_catch
from fourth_official_proving.runner import MatchRun, run_benchmark
from fourth_official_replay import facts_for
from fourth_official_simulator.demo import demo_matchday
from fourth_official_verifier import verify


async def template(moment: object, facts: object) -> Explanation:
    return await explain(moment, facts, [])  # type: ignore[arg-type]


@cache
def demo() -> tuple[MatchRun, ...]:
    return asyncio.run(run_benchmark(demo_matchday(), template))


def test_every_kind_of_lie_is_planted() -> None:
    kinds = Counter(lie.mutation for run in demo() for lie in planted_lies(run))

    assert set(kinds) == set(MUTATIONS)


def test_a_lie_differs_from_the_true_insight_it_was_made_from() -> None:
    for run in demo():
        for lie in planted_lies(run):
            assert lie.insight != lie.original


def test_the_true_insights_the_lies_come_from_pass_the_verifier() -> None:
    (m42, *_) = demo()
    facts = facts_for(m42.record)

    for lie in planted_lies(m42):
        assert verify(lie.original, lie.moment, facts).passed


def test_the_verifier_refuses_every_lie() -> None:
    catch = verifier_catch(demo())

    assert catch.of >= 30
    assert catch.hit == catch.of
