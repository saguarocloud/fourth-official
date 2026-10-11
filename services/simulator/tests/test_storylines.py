"""Storylines: scripted football that the pipeline must later detect, explain and correct."""

from datetime import timedelta
from functools import cache

import pytest

from fourth_official_contracts import (
    CardEvent,
    CarryEvent,
    EventAmended,
    EventVoided,
    FoulEvent,
    GoalEvent,
    PassEvent,
    PeriodEndEvent,
    PossessionChangeEvent,
    PressureEvent,
    SetPieceEvent,
    ShotEvent,
    VarCheckEvent,
    VarDecisionEvent,
    parse_correction,
)
from fourth_official_simulator.engine import SimulatedMatch, play, simulate
from fourth_official_simulator.storylines import (
    Directive,
    RedCard,
    ScorerReassigned,
    ScriptedGoal,
    Storyline,
    StyleShift,
    VarVoid,
)
from matches import BALANCED, setup

STORY = Storyline(
    name="Press collapses, goal ruled out, winner reassigned",
    natural_goals=False,
    directives=(
        ScriptedGoal(club="HCY", minute=12),
        StyleShift(club="NGT", minute=61, pressing=0.15, tempo=0.3, label="NGT press collapses"),
        ScriptedGoal(club="HCY", minute=67),
        VarVoid(goal_minute=67, club="HCY", reason="VAR_OFFSIDE"),
        ScriptedGoal(club="NGT", minute=78),
        ScriptedGoal(club="HCY", minute=89),
        ScorerReassigned(goal_minute=89, club="HCY"),
        RedCard(club="NGT", minute=38),
    ),
)
PRESSING_NGT = BALANCED.with_changes(pressing=0.85)
ON_BALL = (PassEvent, CarryEvent, ShotEvent, SetPieceEvent)


@cache
def story() -> SimulatedMatch:
    return play(setup(4207, away_style=PRESSING_NGT, storyline=STORY))


def goals(match: SimulatedMatch) -> list[GoalEvent]:
    return [e for e in match.events if isinstance(e, GoalEvent)]


def test_a_storyline_match_is_deterministic_and_contract_valid() -> None:
    assert play(setup(4207, away_style=PRESSING_NGT, storyline=STORY)) == story()
    for correction in story().corrections:
        assert parse_correction(correction.to_wire()) == correction


def test_without_a_storyline_play_matches_simulate() -> None:
    assert play(setup(4207)).events == simulate(setup(4207))
    assert play(setup(4207)).corrections == ()


def test_scripted_goals_happen_in_their_minute_and_nothing_else_scores() -> None:
    scored = [(g.team_id, g.clock.minute) for g in goals(story())]

    assert scored == [("HCY", 12), ("HCY", 67), ("NGT", 78), ("HCY", 89)]


def test_a_scripted_goal_is_built_like_a_real_attack() -> None:
    events = story().events
    goal = goals(story())[0]
    shot = next(e for e in events if e.event_id == goal.shot_event_id)
    assert isinstance(shot, ShotEvent)
    before = [e for e in events if e.seq < shot.seq][-1]
    assert isinstance(before, PassEvent)
    assert before.receiver_id == goal.scorer_id
    assert goal.assist_id == before.player_id


def test_the_press_collapses_when_the_storyline_says() -> None:
    def presses_per_minute(start: int, end: int) -> float:
        presses = [
            e
            for e in story().events
            if isinstance(e, PressureEvent) and e.team_id == "NGT" and start <= e.clock.minute < end
        ]
        return len(presses) / (end - start)

    assert presses_per_minute(61, 90) < 0.6 * presses_per_minute(46, 61)


def test_a_voided_goal_is_checked_overturned_and_corrected_after_it_was_published() -> None:
    events = story().events
    void = next(g for g in goals(story()) if g.clock.minute == 67)
    check = next(e for e in events if isinstance(e, VarCheckEvent))
    decision = next(e for e in events if isinstance(e, VarDecisionEvent))
    correction = next(c for c in story().corrections if isinstance(c, EventVoided))

    assert check.target_event_id == decision.target_event_id == void.event_id
    assert (decision.decision, decision.reason) == ("overturned", "offside")
    assert correction.target_event_id == void.event_id
    assert correction.reason == "VAR_OFFSIDE"
    # Long enough that items about the goal have already gone out.
    assert correction.issued_at - void.wall_clock >= timedelta(seconds=60)
    assert correction.issued_at == decision.wall_clock


def test_play_restarts_with_a_free_kick_to_the_defending_side_after_an_overturned_goal() -> None:
    events = story().events
    decision = next(e for e in events if isinstance(e, VarDecisionEvent))
    restart = next(e for e in events if e.seq > decision.seq and isinstance(e, SetPieceEvent))

    assert (restart.kind, restart.team_id) == ("free_kick", "NGT")


def test_later_goals_ignore_the_voided_one_in_the_score() -> None:
    by_minute = {g.clock.minute: g for g in goals(story())}

    assert (by_minute[78].score_after.home, by_minute[78].score_after.away) == (1, 1)
    assert (by_minute[89].score_after.home, by_minute[89].score_after.away) == (2, 1)


def test_the_winners_scorer_is_reassigned_after_the_final_whistle() -> None:
    winner = next(g for g in goals(story()) if g.clock.minute == 89)
    final_whistle = [e for e in story().events if isinstance(e, PeriodEndEvent)][-1]
    amended = next(c for c in story().corrections if isinstance(c, EventAmended))

    assert amended.target_event_id == winner.event_id
    assert amended.reason == "ACCREDITATION_PANEL"
    assert amended.issued_at > final_whistle.wall_clock
    assert amended.changes.scorer_id is not None
    assert amended.changes.scorer_id.startswith("HCY-")
    assert amended.changes.scorer_id not in {winner.scorer_id, winner.assist_id}


def test_a_scripted_red_card_is_shown_in_its_minute() -> None:
    reds = [e for e in story().events if isinstance(e, CardEvent) and e.card == "red"]

    assert [(c.team_id, c.clock.minute) for c in reds] == [("NGT", 38)]


def test_ground_truth_lists_every_storyline_with_its_evidence() -> None:
    truth = story().ground_truth
    kinds = [s.kind for s in truth.storylines]

    assert kinds == [
        "goal",
        "red_card",
        "pressing_collapse",
        "goal",
        "var_overturn",
        "goal",
        "goal",
        "scorer_reassigned",
    ]
    void = next(s for s in truth.storylines if s.kind == "var_overturn")
    assert void.event_ids
    assert void.correction_ids
    collapse = next(s for s in truth.storylines if s.kind == "pressing_collapse")
    assert (collapse.club, collapse.minute) == ("NGT", 61)
    assert (collapse.expected_metric, collapse.expected_direction) == ("pressing_intensity", "down")


def test_corrections_are_ordered_by_issue_time() -> None:
    issued = [c.issued_at for c in story().corrections]

    assert issued == sorted(issued)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_storylines_keep_possession_rules_on_any_seed(seed: int) -> None:
    match = play(setup(seed, away_style=PRESSING_NGT, storyline=STORY))
    holder: str | None = None
    for event in match.events:
        if isinstance(event, PossessionChangeEvent):
            assert event.team_id != holder, event.event_id
            holder = event.team_id
        elif isinstance(event, ON_BALL):
            holder = holder or event.team_id
            assert event.team_id == holder, event.event_id
    assert [(g.team_id, g.clock.minute) for g in goals(match)] == [
        ("HCY", 12),
        ("HCY", 67),
        ("NGT", 78),
        ("HCY", 89),
    ]


def test_the_final_score_in_the_ground_truth_leaves_out_the_voided_goal() -> None:
    final = story().ground_truth.final_score

    assert (final.home, final.away) == (2, 1)


def test_a_sent_off_player_takes_no_further_part() -> None:
    red = next(e for e in story().events if isinstance(e, CardEvent) and e.card == "red")
    later = [e for e in story().events if e.seq > red.seq]

    assert all(red.player_id not in e.model_dump().values() for e in later)


@pytest.mark.parametrize(
    ("directives", "message"),
    [
        ((ScriptedGoal(club="HCY", minute=45),), "not 45"),
        ((ScriptedGoal(club="HCY", minute=90),), "1-89"),
        ((ScriptedGoal(club="HCY", minute=20), RedCard(club="NGT", minute=21)), "too close"),
        ((VarVoid(club="HCY", goal_minute=30),), "no scripted goal"),
        ((ScorerReassigned(club="NGT", goal_minute=30),), "no scripted goal"),
        (
            (
                ScriptedGoal(club="HCY", minute=30),
                VarVoid(club="HCY", goal_minute=30),
                ScorerReassigned(club="HCY", goal_minute=30),
            ),
            "cannot have its scorer reassigned",
        ),
    ],
)
def test_incoherent_storylines_are_refused(directives: tuple[Directive, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Storyline(name="Broken", directives=directives)


def test_a_storyline_name_is_printable_and_bounded() -> None:
    with pytest.raises(ValueError, match="printable"):
        Storyline(name="two\nlines", directives=())


@pytest.mark.parametrize("changes", [{}, {"pressing": 1.5}])
def test_style_shifts_change_valid_dials(changes: dict[str, float]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - either message is right
        StyleShift(club="NGT", minute=60, label="Shift", **changes)


def test_a_storyline_about_a_club_not_in_the_match_is_refused() -> None:
    stray = Storyline(name="Stray", directives=(ScriptedGoal(club="SLT", minute=10),))

    with pytest.raises(ValueError, match="SLT"):
        play(setup(4207, storyline=stray))


def test_a_tactical_shift_without_pressing_is_not_a_pressing_story() -> None:
    deeper = Storyline(
        name="Deeper block",
        directives=(StyleShift(club="HCY", minute=70, label="HCY go direct", directness=0.9),),
    )
    truth = play(setup(4207, storyline=deeper)).ground_truth.storylines

    assert [(t.kind, t.expected_metric) for t in truth] == [("tactical_shift", None)]


def test_a_red_card_for_the_side_in_possession_is_still_a_foul_and_a_free_kick() -> None:
    # Whichever side has the ball at the moment, the sending-off is a foul followed by a restart.
    for seed in range(4200, 4212):
        red = Storyline(name="Red", directives=(RedCard(club="HCY", minute=30),))
        events = play(setup(seed, storyline=red)).events
        card = next(e for e in events if isinstance(e, CardEvent) and e.card == "red")
        foul_ = next(e for e in events if e.event_id == card.foul_event_id)
        assert isinstance(foul_, FoulEvent)
        assert foul_.team_id == "HCY"
        restart = next(e for e in events if e.seq > card.seq and isinstance(e, SetPieceEvent))
        assert restart.team_id == "NGT"
