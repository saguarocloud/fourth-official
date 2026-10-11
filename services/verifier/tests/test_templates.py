"""Template insights: the deterministic last resort for every moment, and always verifiable."""

from dataclasses import replace
from functools import cache

import pytest

from fourth_official_contracts import (
    CLUB_NAMES,
    GoalEvent,
    MetricSnapshot,
    Moment,
    parse_insight,
    snapshot_id_parts,
)
from fourth_official_moments.detector import detect
from fourth_official_simulator.demo import demo_matchday
from fourth_official_simulator.engine import play
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import PreparedMatch, prepare
from fourth_official_stats.snapshots import SnapshotKey, snapshot
from fourth_official_verifier import MatchFacts, render_insight, template_insight, verify
from verifier_fixtures import FACTS, GOAL_MOMENT


def _snapshots(match: PreparedMatch, moments: tuple[Moment, ...]) -> dict[str, MetricSnapshot]:
    found = {}
    for moment in moments:
        for snapshot_id in moment.metric_snapshot_ids:
            parts = snapshot_id_parts(snapshot_id)
            key = SnapshotKey(parts.metric, parts.scope, parts.window)  # type: ignore[arg-type]
            found[snapshot_id] = snapshot(match, as_of_seq=parts.as_of_seq, key=key)
    return found


@cache
def demo() -> list[tuple[MatchFacts, tuple[Moment, ...]]]:
    out = []
    for setup in demo_matchday():
        home, away = setup.home.squad, setup.away.squad
        match = prepare(MatchContext(setup.match_id, home.club, away.club), play(setup).events)
        moments = detect(match)[1]
        facts = MatchFacts(
            match=match,
            club_names={c: CLUB_NAMES[c] for c in (home.club, away.club)},
            player_names={p.player_id: p.name for s in (home, away) for p in s.players},
            snapshots=_snapshots(match, moments),
        )
        out.append((facts, moments))
    return out


def test_every_demo_moment_has_a_template_insight_that_passes_verification() -> None:
    checked = set()
    for facts, moments in demo():
        for moment in moments:
            insight = template_insight(moment, facts)
            verdict = verify(insight, moment, facts)
            assert verdict.passed, (moment.moment_id, verdict.findings)
            assert insight.provenance.produced_by == "template"
            assert parse_insight(insight.to_wire()) == insight
            checked.add(moment.kind)
    assert checked >= {"goal", "big_chance", "red_card", "var_overturn", "pressing_collapse"}


def test_a_goal_template_names_the_scorer_and_the_score() -> None:
    facts, moments = demo()[0]
    goal = next(m for m in moments if m.kind == "goal")
    scored = facts.match.by_seq[goal.as_of_seq]
    assert isinstance(scored, GoalEvent)

    rendered = render_insight(template_insight(goal, facts), facts)[1][0]

    assert facts.player_names[scored.scorer_id] in rendered
    assert "1\u20130" in rendered


@pytest.mark.parametrize("attempt", [1, 3])
def test_the_template_records_its_attempt(attempt: int) -> None:
    facts, moments = demo()[0]

    insight = template_insight(moments[0], facts, attempt=attempt)

    assert insight.insight_id.endswith(f"-a{attempt}")


def test_a_var_overturn_may_cite_the_goal_it_rules_out_once_the_void_lands() -> None:
    facts, moments = demo()[0]
    overturn = next(m for m in moments if m.kind == "var_overturn")
    goal_moment = next(
        m for m in moments if m.kind == "goal" and m.event_ids[-1] == overturn.event_ids[0]
    )
    voided = replace(facts, voided={overturn.event_ids[0]: overturn.as_of_seq})

    assert verify(template_insight(overturn, voided), overturn, voided).passed
    # The goal's own insight was true when it was written; the correction cascade retracts it.
    assert verify(template_insight(goal_moment, voided), goal_moment, voided).passed


def test_a_template_for_an_unexpected_event_is_refused() -> None:
    facts, moments = demo()[0]
    goal = next(m for m in moments if m.kind == "goal")
    wrong = goal.model_copy(update={"kind": "red_card"})

    with pytest.raises(ValueError, match="not a CardEvent"):
        template_insight(wrong, facts)


def test_an_unassisted_goal_has_a_single_claim() -> None:
    # The fixture's scorer builder uses shirt 9, which the generated squad does not have.
    facts = replace(FACTS, player_names={**FACTS.player_names, "HCY-09": "Ines Okafor"})
    insight = template_insight(GOAL_MOMENT, facts)

    assert len(insight.claims) == 1
    assert verify(insight, GOAL_MOMENT, facts).passed


@pytest.mark.parametrize(
    ("kind", "words"),
    [("pressing_surge", "rises to"), ("momentum_swing", "momentum")],
)
def test_other_shifts_have_templates_too(kind: str, words: str) -> None:
    facts, moments = demo()[0]
    collapse = next(m for m in moments if m.kind == "pressing_collapse")
    shifted = collapse.model_copy(update={"kind": kind})
    if kind == "momentum_swing":
        shift = collapse.shifts[0].model_copy(update={"metric": "momentum"})
        shifted = shifted.model_copy(update={"shifts": (shift,)})

    rendered = render_insight(template_insight(shifted, facts), facts)[1][0]

    assert words in rendered


def test_a_moment_with_no_template_and_no_shift_is_refused() -> None:
    facts, moments = demo()[0]
    goal = next(m for m in moments if m.kind == "goal")

    with pytest.raises(ValueError, match="no template"):
        template_insight(goal.model_copy(update={"kind": "momentum_swing"}), facts)
