"""Template insights: the deterministic last resort when no model insight passes verification.

Each moment kind has one plain template, phrased in each partner's language and built only from
references, so it passes the Verifier by construction. Templates avoid number words ("ten men",
"five minutes"): numbers are references.
"""

from fourth_official_contracts import (
    CardEvent,
    Claim,
    ClaimType,
    Evidence,
    GoalEvent,
    Insight,
    Locale,
    LocalizedInsight,
    MatchEvent,
    Moment,
    Provenance,
    ShotEvent,
    TenantId,
    VarDecisionEvent,
    insight_id_for,
    item_id_for,
)
from fourth_official_contracts.tenants import TENANT_LOCALES
from fourth_official_verifier.facts import MatchFacts

TEMPLATE_PROVENANCE = Provenance(
    agent="template", prompt_version="v1.0", model="none", produced_by="template"
)

Line = tuple[ClaimType, str]

# Every template in each partner's language. Placeholders are filled with references only, so
# every language passes the Verifier by construction (a test proves it for every demo moment).
PHRASES: dict[Locale, dict[str, str]] = {
    "en-GB": {
        "goal.headline": "{club} score",
        "goal": "{scorer} scores for {club} at {minute}: {score}.",
        "assist": "{assist} provides the assist.",
        "chance.headline": "{club} go close",
        "chance.penalty": "{player} misses a penalty for {club} at {minute}.",
        "chance.close": "{player} goes close for {club} at {minute}.",
        "red.headline": "{club} down a player",
        "red": "{player} is sent off at {minute}, leaving {club} a player short.",
        "red.second": "{player} is sent off at {minute}, leaving {club} a player short.",
        "var.headline": "VAR rules out a {club} goal",
        "var": "VAR rules out the {club} goal from {target} for {reason}.",
        "collapse.headline": "{club} ease off the press",
        "collapse": "{club}'s pressing rate falls to {after} per opponent touch, from {before}.",
        "surge.headline": "{club} step up the press",
        "surge": "{club}'s pressing rate rises to {after} per opponent touch, from {before}.",
        "shift.headline": "{club} change their game",
        "shift": "The {metric} for {club} is now {after}, from {before}.",
    },
    "es-MX": {
        "goal.headline": "Gol de {club}",
        "goal": "{scorer} marca para {club} en el {minute}: {score}.",
        "assist": "{assist} da la asistencia.",
        "chance.headline": "Ocasión de {club}",
        "chance.penalty": "{player} falla un penal para {club} en el {minute}.",
        "chance.close": "{player} roza el gol para {club} en el {minute}.",
        "red.headline": "{club} con un jugador menos",
        "red": "{player} es expulsado en el {minute} y {club} se queda con un jugador menos.",
        "red.second": (
            "{player} es expulsado en el {minute} y {club} se queda con un jugador menos."
        ),
        "var.headline": "El VAR anula un gol de {club}",
        "var": "El VAR anula el gol de {club} del {target} por {reason}.",
        "collapse.headline": "{club} baja la presión",
        "collapse": "La presión de {club} baja a {after} por toque rival, desde {before}.",
        "surge.headline": "{club} sube la presión",
        "surge": "La presión de {club} sube a {after} por toque rival, desde {before}.",
        "shift.headline": "{club} cambia su juego",
        "shift": "El valor de {metric} para {club} es ahora {after}, desde {before}.",
    },
    "de-DE": {
        "goal.headline": "Tor für {club}",
        "goal": "{scorer} trifft in Minute {minute} für {club} zum {score}.",
        "assist": "{assist} bereitet das Tor vor.",
        "chance.headline": "Große Chance für {club}",
        "chance.penalty": "{player} vergibt in Minute {minute} einen Elfmeter für {club}.",
        "chance.close": "{player} scheitert in Minute {minute} knapp für {club}.",
        "red.headline": "{club} in Unterzahl",
        "red": "{player} sieht in Minute {minute} Rot, {club} spielt in Unterzahl.",
        # A second yellow is "Gelb-Rot" in German, never "Rot".
        "red.second": "{player} sieht in Minute {minute} Gelb-Rot, {club} spielt in Unterzahl.",
        "var.headline": "Videobeweis nimmt {club} ein Tor",
        "var": (
            "Der Videobeweis nimmt das Tor von {club} aus Minute {target} wegen {reason} zurück."
        ),
        "collapse.headline": "{club} lässt im Pressing nach",
        "collapse": "Die Pressingquote von {club} fällt auf {after} pro Ballkontakt, von {before}.",
        "surge.headline": "{club} erhöht das Pressing",
        "surge": "Die Pressingquote von {club} steigt auf {after} pro Ballkontakt, von {before}.",
        "shift.headline": "{club} ändert das Spiel",
        "shift": "Der Wert für {metric} von {club} liegt jetzt bei {after}, nach {before}.",
    },
}
REASONS: dict[Locale, dict[str, str]] = {
    "en-GB": {"offside": "offside", "foul": "a foul", "handball": "handball", "none": "a review"},
    "es-MX": {"offside": "fuera de juego", "foul": "falta", "handball": "mano", "none": "revisión"},
    "de-DE": {
        "offside": "Abseits",
        "foul": "Foulspiel",
        "handball": "Handspiel",
        "none": "einer Überprüfung",
    },
}
METRICS: dict[Locale, dict[str, str]] = {
    "en-GB": {},
    "es-MX": {
        "possession": "posesión",
        "field_tilt": "dominio territorial",
        "passes": "pases",
        "pass_completion": "precisión de pase",
        "shots": "remates",
        "shots_on_target": "remates a puerta",
        "xg": "xG",
        "ppda": "PPDA",
        "pressing_intensity": "intensidad de presión",
        "momentum": "impulso",
        "control_chaos": "control del juego",
    },
    "de-DE": {
        "possession": "Ballbesitz",
        "field_tilt": "Feldanteil",
        "passes": "Pässe",
        "pass_completion": "Passquote",
        "shots": "Schüsse",
        "shots_on_target": "Schüsse aufs Tor",
        "xg": "xG",
        "ppda": "PPDA",
        "pressing_intensity": "Pressingintensität",
        "momentum": "Momentum",
        "control_chaos": "Spielkontrolle",
    },
}


def _event[E: MatchEvent](facts: MatchFacts, event_id: str, kind: type[E]) -> E:
    event = next((e for e in facts.match.events if e.event_id == event_id), None)
    if not isinstance(event, kind):
        raise ValueError(f"{event_id} is not a {kind.__name__}")
    return event


def _club(code: str) -> str:
    return f"{{{{club:{code}}}}}"


def _player(player_id: str) -> str:
    return f"{{{{player:{player_id}}}}}"


def _minute(minute: int) -> str:
    return f"{{{{minute:{minute}}}}}"


def _goal(moment: Moment, facts: MatchFacts, say: dict[str, str]) -> tuple[str, list[Line]]:
    goal = _event(facts, moment.event_ids[-1], GoalEvent)
    club = _club(goal.team_id)
    line = say["goal"].format(
        scorer=_player(goal.scorer_id),
        club=club,
        minute=_minute(goal.clock.minute),
        score="{{score}}",
    )
    lines: list[Line] = [("stat", line)]
    if goal.assist_id:
        lines.append(("stat", say["assist"].format(assist=_player(goal.assist_id))))
    return say["goal.headline"].format(club=club), lines


def _big_chance(moment: Moment, facts: MatchFacts, say: dict[str, str]) -> tuple[str, list[Line]]:
    shot = _event(facts, moment.event_ids[-1], ShotEvent)
    key = "chance.penalty" if len(moment.event_ids) > 1 else "chance.close"
    club = _club(shot.team_id)
    line = say[key].format(
        player=_player(shot.player_id), club=club, minute=_minute(shot.clock.minute)
    )
    return say["chance.headline"].format(club=club), [("stat", line)]


def _red_card(moment: Moment, facts: MatchFacts, say: dict[str, str]) -> tuple[str, list[Line]]:
    card = _event(facts, moment.event_ids[-1], CardEvent)
    club = _club(card.team_id)
    key = "red.second" if card.card == "second_yellow" else "red"
    line = say[key].format(
        player=_player(card.player_id), club=club, minute=_minute(card.clock.minute)
    )
    return say["red.headline"].format(club=club), [("stat", line)]


def _var_overturn(
    moment: Moment, facts: MatchFacts, say: dict[str, str], locale: Locale
) -> tuple[str, list[Line]]:
    decision = _event(facts, moment.event_ids[-1], VarDecisionEvent)
    target = _event(facts, moment.event_ids[0], GoalEvent)
    club = _club(moment.club)
    line = say["var"].format(
        club=club, target=_minute(target.clock.minute), reason=REASONS[locale][decision.reason]
    )
    return say["var.headline"].format(club=club), [("milestone", line)]


def _shift(moment: Moment, say: dict[str, str], locale: Locale) -> tuple[str, list[Line]]:
    shift = moment.shifts[0]
    club = _club(moment.club)
    after = f"{{{{value:{shift.after_snapshot_id}}}}}"
    before = f"{{{{value:{shift.before_snapshot_id}}}}}"
    key = {"pressing_collapse": "collapse", "pressing_surge": "surge"}.get(moment.kind, "shift")
    metric = METRICS[locale].get(shift.metric, shift.metric.replace("_", " "))
    line = say[key].format(club=club, after=after, before=before, metric=metric)
    return say[f"{key}.headline"].format(club=club), [("comparison", line)]


def _phrased(moment: Moment, facts: MatchFacts, locale: Locale) -> tuple[str, list[Line]]:
    say = PHRASES[locale]
    if moment.kind == "goal":
        return _goal(moment, facts, say)
    if moment.kind == "big_chance":
        return _big_chance(moment, facts, say)
    if moment.kind == "red_card":
        return _red_card(moment, facts, say)
    if moment.kind == "var_overturn":
        return _var_overturn(moment, facts, say, locale)
    if not moment.shifts:
        raise ValueError(f"no template for a {moment.kind} moment without a metric shift")
    return _shift(moment, say, locale)


def _claims(moment: Moment, lines: list[Line]) -> tuple[Claim, ...]:
    evidence = Evidence(event_ids=moment.event_ids, metric_snapshot_ids=moment.metric_snapshot_ids)
    return tuple(
        Claim(claim_id=f"cl-{n}", type=kind, text=text, evidence=evidence)
        for n, (kind, text) in enumerate(lines, start=1)
    )


def template_insight(moment: Moment, facts: MatchFacts, *, attempt: int = 1) -> Insight:
    """A plain, verifiable insight for the moment, from its own evidence."""
    headline, lines = _phrased(moment, facts, "en-GB")
    return Insight(
        insight_id=insight_id_for(moment.moment_id, attempt=attempt),
        match_id=moment.match_id,
        moment_id=moment.moment_id,
        as_of_seq=moment.as_of_seq,
        locale="en",
        headline=headline,
        claims=_claims(moment, lines),
        provenance=TEMPLATE_PROVENANCE,
    )


def template_localized(
    moment: Moment,
    facts: MatchFacts,
    *,
    tenant_id: TenantId,
    insight_id: str,
    policy_version: int,
    version: int = 1,
) -> LocalizedInsight:
    """A plain, verifiable version of the moment's insight in the partner's language: the last
    resort when no localised draft passes."""
    locale = TENANT_LOCALES[tenant_id]
    headline, lines = _phrased(moment, facts, locale)
    return LocalizedInsight(
        item_id=item_id_for(tenant_id, insight_id, version=version),
        tenant_id=tenant_id,
        locale=locale,
        insight_id=insight_id,
        match_id=moment.match_id,
        moment_id=moment.moment_id,
        as_of_seq=moment.as_of_seq,
        version=version,
        headline=headline,
        claims=_claims(moment, lines),
        provenance=TEMPLATE_PROVENANCE,
        policy_version=policy_version,
    )
