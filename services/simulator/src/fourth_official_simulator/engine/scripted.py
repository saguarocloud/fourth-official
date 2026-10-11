"""Storyline moments played into the match: style shifts, goals on cue, VAR overturns, red cards,
and the corrections and ground truth they leave behind.

Scripted moments are real football: a goal is a completed pass into the box and a shot that goes
in; a VAR overturn is a check, a decision and a free kick to the defending side. They only decide
*that* something happens and roughly when, never break a rule of the match.
"""

import math
import random
from dataclasses import replace
from datetime import timedelta
from typing import Literal

from fourth_official_contracts import (
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    Amendment,
    CardEvent,
    Correction,
    EventAmended,
    EventVoided,
    FoulEvent,
    GoalEvent,
    InterceptionEvent,
    MatchEvent,
    PassEvent,
    StorylineTruth,
    VarCheckEvent,
    VarDecisionEvent,
)
from fourth_official_simulator.engine.actions import (
    PENALTY_SPOT,
    BodyPart,
    Strike,
    award_goal,
    foul,
    kick_off_after_goal,
    penalty_kick,
    strike_shot,
)
from fourth_official_simulator.engine.restarts import change_possession, restart
from fourth_official_simulator.engine.state import (
    Emitter,
    MatchState,
    ScoredGoal,
    Step,
    StoryLog,
    advance,
    attackers,
    defenders,
    pick,
    point,
    side,
    wait,
    with_side,
    zone_at,
)
from fourth_official_simulator.pitch import Zone, pitch_to_attacking, zone_of
from fourth_official_simulator.squads import Player, Position
from fourth_official_simulator.storylines import (
    Moment,
    RedCard,
    ScriptedGoal,
    Storyline,
    StyleShift,
    VarReason,
    VarVoid,
    period_of,
)

# A moment starts once play is within this many seconds of its minute; the clock then runs on to
# a few seconds into the minute.
LOOKAHEAD_SECONDS = 60
# A scripted goal is scored from a pass into the box, about 15 m out.
SCORING_PROGRESS = 0.86
# VAR: the check opens soon after the goal; the decision comes a minute or more later, by which
# time items about the goal have gone out.
VAR_CHECK_AFTER = 20
VAR_DECISION_AFTER = (45, 70)
VAR_DECISION_REASON: dict[VarReason, Literal["offside", "foul", "handball"]] = {
    "VAR_OFFSIDE": "offside",
    "VAR_FOUL": "foul",
    "VAR_HANDBALL": "handball",
}
# The accreditation panel sits after the final whistle.
PANEL_AFTER_FINAL_WHISTLE = timedelta(minutes=25)


def _truth(state: MatchState, truth: StorylineTruth) -> MatchState:
    return replace(state, story=replace(state.story, truths=(*state.story.truths, truth)))


def _correction(state: MatchState, correction: Correction) -> MatchState:
    corrections = (*state.story.corrections, correction)
    return replace(state, story=replace(state.story, corrections=corrections))


def correction_id(match_id: str, number: int) -> str:
    """Corrections are numbered per match, like events: `c-m42-01`."""
    return f"c-{match_id}-{number:02d}"


# --- Style shifts ---------------------------------------------------------------------------------


def _shift_truth(shift: StyleShift, before: float, after: float) -> StorylineTruth:
    if "pressing" in shift.changes and after != before:
        down = after < before
        return StorylineTruth(
            kind="pressing_collapse" if down else "pressing_surge",
            club=shift.club,
            minute=shift.minute,
            label=shift.label,
            event_ids=(),
            correction_ids=(),
            expected_metric="pressing_intensity",
            expected_direction="down" if down else "up",
        )
    return StorylineTruth(
        kind="tactical_shift",
        club=shift.club,
        minute=shift.minute,
        label=shift.label,
        event_ids=(),
        correction_ids=(),
        expected_metric=None,
        expected_direction=None,
    )


def apply_styles(state: MatchState, emit: Emitter, story: Storyline) -> MatchState:
    """Both sides play in the style the storyline gives them for the current minute."""
    minute = state.elapsed // 60
    for home, team in ((True, emit.setup.home), (False, emit.setup.away)):
        current = side(state, home)
        style = story.style_at(current.club, team.style, minute)
        if style != current.style:
            state = with_side(state, home, replace(current, style=style))
    for index, shift in enumerate(story.shifts):
        if index not in state.story.shifts_seen and shift.minute <= minute:
            base = emit.setup.home if shift.club == emit.setup.home.squad.club else emit.setup.away
            before = story.style_at(shift.club, base.style, shift.minute - 1).pressing
            after = story.style_at(shift.club, base.style, shift.minute).pressing
            state = _truth(state, _shift_truth(shift, before, after))
            seen = state.story.shifts_seen | {index}
            state = replace(state, story=replace(state.story, shifts_seen=seen))
    return state


# --- Moments --------------------------------------------------------------------------------------


def due_moment(state: MatchState, story: Storyline) -> tuple[int, Moment] | None:
    """The next scripted moment whose minute play has reached, if any."""
    for index, moment in enumerate(story.moments):
        if (
            index not in state.story.moments_done
            and period_of(moment.minute) == state.period
            and state.elapsed + LOOKAHEAD_SECONDS >= moment.minute * 60
        ):
            return index, moment
    return None


def play_moment(
    state: MatchState,
    emit: Emitter,
    rng: random.Random,
    *,
    story: Storyline,
    due: tuple[int, Moment],
) -> Step:
    index, moment = due
    done = state.story.moments_done | {index}
    state = replace(state, story=replace(state.story, moments_done=done))
    into_minute = moment.minute * 60 + rng.randint(5, 30)
    state = replace(state, elapsed=min(max(state.elapsed, into_minute), state.period_end))
    if isinstance(moment, ScriptedGoal):
        return _scripted_goal(state, emit, rng, goal=moment, void=story.void_for(moment))
    return _red_card(state, emit, rng, moment)


def _win_ball(state: MatchState, emit: Emitter, rng: random.Random, home: bool) -> Step:
    """`home`'s side intercepts in midfield, if it does not have the ball already."""
    if state.home_in_possession == home:
        return state, []
    # The ball is won where it is: the same spot, seen from the other end.
    progress, lateral = 1.0 - state.progress, 1.0 - state.lateral
    interceptor = pick(side(state, home).on_pitch, zone_of(progress, lateral), rng, keepers=False)
    club = side(state, home).club
    state, changed = change_possession(
        state, emit, "interception", carrier=interceptor, progress=progress, lateral=lateral
    )
    at = point(state, progress, lateral)
    state, cut_out = emit.stamp(
        state,
        lambda env: InterceptionEvent(
            **env, type="INTERCEPTION", team_id=club, player_id=interceptor.player_id, at=at
        ),
    )
    return state, [*changed, cut_out]


def _scorer(team: tuple[Player, ...], passer: Player, rng: random.Random) -> Player:
    for position in (Position.FORWARD, Position.MIDFIELDER, Position.DEFENDER):
        candidates = [p for p in team if p.position is position and p != passer]
        if candidates:
            return rng.choice(candidates)
    raise ValueError("no outfield player left to score")


def _play_out_from_keeper(state: MatchState, emit: Emitter, rng: random.Random) -> Step:
    """A keeper on the ball first finds a team-mate nearby; keepers do not set up goals from their
    own box."""
    if state.carrier.position is not Position.GOALKEEPER:
        return state, []
    team = attackers(state)
    keeper_ = state.carrier
    receiver = pick(team.on_pitch, Zone.DEFENSIVE_THIRD, rng, exclude=keeper_, keepers=False)
    end_progress = min(state.progress + rng.uniform(0.1, 0.2), 0.35)
    end_lateral = min(max(state.lateral + rng.uniform(-0.3, 0.3), 0.05), 0.95)
    distance = math.hypot(
        (end_progress - state.progress) * PITCH_LENGTH_M,
        (end_lateral - state.lateral) * PITCH_WIDTH_M,
    )
    origin, end = (
        point(state, state.progress, state.lateral),
        point(state, end_progress, end_lateral),
    )
    state, made = emit.stamp(
        state,
        lambda env: PassEvent(
            **env,
            type="PASS",
            team_id=team.club,
            player_id=keeper_.player_id,
            origin=origin,
            end=end,
            outcome="complete",
            receiver_id=receiver.player_id,
            kind="ground",
            speed_kmh=round(min(140.0, 30 + distance * 1.4), 1),
        ),
    )
    moved = replace(
        advance(state, 2.2 + distance / 16),
        carrier=receiver,
        progress=end_progress,
        lateral=end_lateral,
        last_passer=keeper_,
        last_delivery="ground",
        dribbled=False,
    )
    return moved, [made]


def _pass_into_box(state: MatchState, emit: Emitter, rng: random.Random) -> Step:
    """The carrier finds a team-mate in the box with a completed pass."""
    team = attackers(state)
    passer = state.carrier
    receiver = _scorer(team.on_pitch, passer, rng)
    end_progress, end_lateral = SCORING_PROGRESS, rng.uniform(0.38, 0.62)
    distance = math.hypot(
        (end_progress - state.progress) * PITCH_LENGTH_M,
        (end_lateral - state.lateral) * PITCH_WIDTH_M,
    )
    origin, end = (
        point(state, state.progress, state.lateral),
        point(state, end_progress, end_lateral),
    )
    speed = round(min(140.0, 30 + distance * 1.4), 1)
    state, made = emit.stamp(
        state,
        lambda env: PassEvent(
            **env,
            type="PASS",
            team_id=team.club,
            player_id=passer.player_id,
            origin=origin,
            end=end,
            outcome="complete",
            receiver_id=receiver.player_id,
            kind="through" if distance <= 35 else "lofted",
            speed_kmh=speed,
        ),
    )
    state = replace(
        advance(state, 2.2 + distance / 16),
        carrier=receiver,
        progress=end_progress,
        lateral=end_lateral,
        last_passer=passer,
        last_delivery=made.kind,
        dribbled=False,
    )
    return state, [made]


def _scripted_goal(
    state: MatchState,
    emit: Emitter,
    rng: random.Random,
    *,
    goal: ScriptedGoal,
    void: VarVoid | None,
) -> Step:
    home = goal.club == state.home.club
    state, won = _win_ball(state, emit, rng, home)
    state, played_out = _play_out_from_keeper(state, emit, rng)
    passer = state.carrier
    state, delivered = _pass_into_box(state, emit, rng)
    foot: BodyPart = rng.choice(("right_foot", "left_foot"))
    state, shot = strike_shot(
        state, emit, Strike("goal", foot, round(rng.uniform(95, 120), 1), 0.25)
    )
    state, scored = award_goal(state, emit, shot=shot, passer=passer)
    on_pitch = tuple(
        p.player_id for p in attackers(state).on_pitch if p.position is not Position.GOALKEEPER
    )
    goals = (*state.story.goals, ScoredGoal(goal, scored, on_pitch))
    state = replace(state, story=replace(state.story, goals=goals))
    state = _truth(
        state,
        StorylineTruth(
            kind="goal",
            club=goal.club,
            minute=scored.clock.minute,
            label=f"{goal.club} goal by {scored.scorer_id}",
            event_ids=(delivered[0].event_id, shot.event_id, scored.event_id),
            correction_ids=(),
            expected_metric=None,
            expected_direction=None,
        ),
    )
    if void is None:
        state, kick_off = kick_off_after_goal(state, emit, rng, home_scored=home)
        return state, [*won, *played_out, *delivered, shot, scored, *kick_off]
    state, reviewed = _var_overturn(state, emit, rng, goal=scored, void=void)
    return state, [*won, *played_out, *delivered, shot, scored, *reviewed]


def _var_overturn(
    state: MatchState, emit: Emitter, rng: random.Random, *, goal: GoalEvent, void: VarVoid
) -> Step:
    """VAR checks the goal and rules it out; the score goes back and the defenders restart."""
    home_scored = state.home_in_possession
    state, check = emit.stamp(
        wait(state, VAR_CHECK_AFTER),
        lambda env: VarCheckEvent(
            **env, type="VAR_CHECK", target_event_id=goal.event_id, reason="goal"
        ),
    )
    state, decision = emit.stamp(
        wait(state, rng.randint(*VAR_DECISION_AFTER)),
        lambda env: VarDecisionEvent(
            **env,
            type="VAR_DECISION",
            target_event_id=goal.event_id,
            decision="overturned",
            reason=VAR_DECISION_REASON[void.reason],
        ),
    )
    issued = correction_id(goal.match_id, len(state.story.corrections) + 1)
    state = _correction(
        state,
        EventVoided(
            correction_id=issued,
            match_id=goal.match_id,
            reason=void.reason,
            issued_at=decision.wall_clock,
            target_event_id=goal.event_id,
            new_version=2,
            kind="EVENT_VOIDED",
        ),
    )
    state = _truth(
        state,
        StorylineTruth(
            kind="var_overturn",
            club=void.club,
            minute=goal.clock.minute,
            label=f"{void.club} goal ruled out ({VAR_DECISION_REASON[void.reason]})",
            event_ids=(goal.event_id, check.event_id, decision.event_id),
            correction_ids=(issued,),
            expected_metric=None,
            expected_direction=None,
        ),
    )
    state = replace(
        state,
        home_score=state.home_score - home_scored,
        away_score=state.away_score - (not home_scored),
    )
    state, free_kick = restart(
        state,
        emit,
        rng,
        "free_kick",
        home_in_possession=not home_scored,
        progress=1.0 - state.progress,
        lateral=1.0 - state.lateral,
    )
    return state, [check, decision, *free_kick]


def _red_card(state: MatchState, emit: Emitter, rng: random.Random, red: RedCard) -> Step:
    """A player of the club is sent off for a foul, whether it is defending or attacking."""
    home = red.club == state.home.club
    if state.home_in_possession != home:
        state, events = foul(state, emit, rng, card="red")
    else:
        state, events = _foul_by_attacker(state, emit, rng)
    committed = next(e for e in events if isinstance(e, FoulEvent))
    shown = next(e for e in events if isinstance(e, CardEvent))
    state = _truth(
        state,
        StorylineTruth(
            kind="red_card",
            club=red.club,
            minute=shown.clock.minute,
            label=f"{red.club} down to ten",
            event_ids=(committed.event_id, shown.event_id),
            correction_ids=(),
            expected_metric=None,
            expected_direction=None,
        ),
    )
    return state, events


def _foul_by_attacker(state: MatchState, emit: Emitter, rng: random.Random) -> Step:
    """A player of the side in possession fouls an opponent and is sent off. The opponents take a
    free kick there, or a penalty if the foul was in the offender's own box."""
    team, opponents = attackers(state), defenders(state)
    offender = rng.choice(
        [p for p in team.on_pitch if p != state.carrier and p.position is not Position.GOALKEEPER]
    )
    victim = pick(opponents.on_pitch, Zone.MIDDLE_THIRD, rng, keepers=False)
    at = point(state, state.progress, state.lateral)
    state, committed = emit.stamp(
        state,
        lambda env: FoulEvent(
            **env,
            type="FOUL",
            team_id=team.club,
            player_id=offender.player_id,
            at=at,
            victim_id=victim.player_id,
        ),
    )
    state, shown = emit.stamp(
        state,
        lambda env: CardEvent(
            **env,
            type="CARD",
            team_id=team.club,
            player_id=offender.player_id,
            card="red",
            foul_event_id=committed.event_id,
        ),
    )
    reduced = replace(team, on_pitch=tuple(p for p in team.on_pitch if p != offender))
    state = advance(with_side(state, state.home_in_possession, reduced), 40)
    # The opponents restart where the foul happened, seen from their end.
    taking = not state.home_in_possession
    progress, lateral = pitch_to_attacking(at.x, at.y, home=taking, period=state.period)
    if zone_at(at, home=taking, period=state.period) is Zone.BOX:
        state, awarded = restart(
            state,
            emit,
            rng,
            "penalty",
            home_in_possession=taking,
            progress=PENALTY_SPOT,
            lateral=0.5,
            cause="foul",
        )
        state, kick = penalty_kick(state, emit, rng)
        return state, [committed, shown, *awarded, *kick]
    state, free_kick = restart(
        state,
        emit,
        rng,
        "free_kick",
        home_in_possession=taking,
        progress=progress,
        lateral=lateral,
        cause="foul",
    )
    return state, [committed, shown, *free_kick]


# --- After the final whistle ----------------------------------------------------------------------


def reassign_scorers(
    log: StoryLog, rng: random.Random, *, story: Storyline, final_whistle: MatchEvent
) -> StoryLog:
    """The accreditation panel credits scripted goals to a different player of the same side."""
    for directive in story.reassignments:
        scored = next(
            g
            for g in log.goals
            if (g.directive.club, g.directive.minute) == (directive.club, directive.goal_minute)
        )
        goal = scored.event
        others = sorted(set(scored.on_pitch) - {goal.scorer_id, goal.assist_id})
        new_scorer = rng.choice(others)
        issued = correction_id(goal.match_id, len(log.corrections) + 1)
        correction = EventAmended(
            correction_id=issued,
            match_id=goal.match_id,
            reason="ACCREDITATION_PANEL",
            issued_at=final_whistle.wall_clock + PANEL_AFTER_FINAL_WHISTLE,
            target_event_id=goal.event_id,
            new_version=2,
            kind="EVENT_AMENDED",
            changes=Amendment(scorer_id=new_scorer),
        )
        truth = StorylineTruth(
            kind="scorer_reassigned",
            club=directive.club,
            minute=goal.clock.minute,
            label=f"{directive.club} goal credited to {new_scorer}",
            event_ids=(goal.event_id,),
            correction_ids=(issued,),
            expected_metric=None,
            expected_direction=None,
        )
        log = replace(log, corrections=(*log.corrections, correction), truths=(*log.truths, truth))
    return log
