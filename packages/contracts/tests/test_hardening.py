"""Boundary hardening: strict types, bounded values, canonical identifiers, coherent references."""

import json
from typing import get_args

import pytest
from pydantic import ValidationError

from builders import envelope, goal, shot
from fourth_official_contracts import (
    MATCH_EVENT_TYPES,
    EventAmended,
    GoalEvent,
    parse_correction,
    parse_correction_json,
    parse_match_event,
    parse_match_event_json,
)
from fourth_official_contracts.schema import export_schemas


# --- Strict types: what the schema says is what Python accepts -----------------------------
@pytest.mark.parametrize(
    ("builder", "field", "value"),
    [
        (shot, "seq", "187"),
        (shot, "seq", 187.0),
        (shot, "wallClock", 1_700_000_000),
        (goal, "ownGoal", "yes"),
        (goal, "ownGoal", 1),
        (shot, "speedKmh", "104.2"),
    ],
)
def test_refuses_values_that_only_coerce_to_the_right_type(
    builder: object, field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        parse_match_event(builder(**{field: value}))  # type: ignore[operator]


def test_refuses_snake_case_keys_on_the_wire() -> None:
    raw = shot()
    raw["event_id"] = raw.pop("eventId")

    with pytest.raises(ValidationError):
        parse_match_event(raw)


def test_parses_json_text_directly() -> None:
    assert parse_match_event_json(json.dumps(shot())).to_wire() == shot()


def test_validation_errors_do_not_echo_the_input() -> None:
    with pytest.raises(ValidationError) as caught:
        parse_match_event(shot(playerId="X" * 50))

    assert "XXXX" not in str(caught.value)


# --- Canonical, bounded identifiers and numbers -----------------------------------------------
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("matchId", "m" + chr(0x0661) + chr(0x0662)),  # Arabic-Indic digits
        ("eventId", "m42-e" + "".join(chr(0xFF10 + d) for d in (0, 1, 8, 7))),  # fullwidth
        ("matchId", "m" + "9" * 13),
        ("seq", 10_000_001),
        ("version", 1_001),
        ("speedKmh", float("nan")),
    ],
)
def test_refuses_non_canonical_or_unbounded_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        parse_match_event(shot(**{field: value}))


def test_refuses_an_implausible_score() -> None:
    with pytest.raises(ValidationError):
        parse_match_event(goal(scoreAfter={"home": 100, "away": 0}))


def test_normalises_timestamps_with_an_offset_to_utc_milliseconds() -> None:
    event = parse_match_event(shot(wallClock="2026-10-24T17:07:12.4005+02:00"))

    assert event.to_wire()["wallClock"] == "2026-10-24T15:07:12.400Z"


# --- References between events stay inside the match ------------------------------------------
@pytest.mark.parametrize(
    ("raw"),
    [
        goal(shotEventId="m41-e0187"),
        goal(shotEventId="m42-e0188"),  # its own id
        envelope(type="SAVE", teamId="NGT", playerId="NGT-01", shotEventId="m99-e0001"),
        envelope(type="VAR_CHECK", targetEventId="m99-e0001", reason="goal"),
    ],
)
def test_refuses_references_outside_the_match_or_to_itself(raw: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        parse_match_event(raw)


@pytest.mark.parametrize(("decision", "reason"), [("overturned", "none"), ("confirmed", "offside")])
def test_refuses_contradictory_var_decisions(decision: str, reason: str) -> None:
    with pytest.raises(ValidationError):
        parse_match_event(
            envelope(
                type="VAR_DECISION", targetEventId="m42-e0188", decision=decision, reason=reason
            )
        )


def test_an_own_goal_needs_no_shot() -> None:
    event = parse_match_event(
        goal(scorerId="NGT-05", assistId=None, ownGoal=True, shotEventId=None)
    )

    assert isinstance(event, GoalEvent)
    assert event.to_wire()["shotEventId"] is None


def test_a_normal_goal_needs_its_shot() -> None:
    with pytest.raises(ValidationError, match="shot"):
        parse_match_event(goal(shotEventId=None))


def test_nullable_fields_keep_their_key_on_the_wire() -> None:
    assert "assistId" in parse_match_event(goal(assistId=None)).to_wire()


def test_model_dump_json_is_camel_case_by_default() -> None:
    assert '"eventId"' in parse_match_event(shot()).model_dump_json()


# --- Corrections ---------------------------------------------------------------------------------
CORRECTION = {
    "correctionId": "c-m42-04",
    "matchId": "m42",
    "targetEventId": "m42-e0188",
    "kind": "EVENT_AMENDED",
    "reason": "ACCREDITATION_PANEL",
    "issuedAt": "2026-10-24T16:01:00.000Z",
    "newVersion": 3,
}


@pytest.mark.parametrize("changes", [{"scorerId": None}, {"ownGoal": None}, {"card": None}])
def test_an_amendment_cannot_set_a_required_fact_to_null(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        parse_correction(CORRECTION | {"changes": changes})


def test_an_amendment_can_remove_an_assist() -> None:
    correction = parse_correction(CORRECTION | {"changes": {"assistId": None}})

    assert isinstance(correction, EventAmended)
    assert correction.to_wire()["changes"] == {"assistId": None}


def test_an_amendment_cannot_mix_goal_and_card_changes() -> None:
    with pytest.raises(ValidationError, match="goal"):
        parse_correction(CORRECTION | {"changes": {"card": "red", "ownGoal": True}})


def test_a_second_yellow_card_amendment_is_valid() -> None:
    assert parse_correction(CORRECTION | {"changes": {"card": "second_yellow"}})


# --- The catalogue and the published schema -----------------------------------------------------
def test_the_event_catalogue_has_nineteen_types() -> None:
    assert len(MATCH_EVENT_TYPES) == 19


def test_the_published_schema_discriminates_every_event_type() -> None:
    schema = export_schemas()["match-event.schema.json"]
    mapping = schema["discriminator"]["mapping"]

    declared = {get_args(cls.model_fields["type"].annotation)[0] for cls in MATCH_EVENT_TYPES}

    assert set(mapping) == declared


def test_accepts_whole_numbers_for_decimal_fields_as_json_encoders_write_them() -> None:
    event = parse_match_event_json(json.dumps(shot(origin={"x": 88, "y": 41}, speedKmh=104)))

    assert event.to_wire()["origin"] == {"x": 88.0, "y": 41.0}


def test_parses_correction_json_text_directly() -> None:
    raw = CORRECTION | {"changes": {"scorerId": "HCY-11"}}

    assert parse_correction_json(json.dumps(raw)).to_wire() == raw


def test_every_dump_path_omits_unchanged_amendment_fields() -> None:
    correction = parse_correction(CORRECTION | {"changes": {"scorerId": "HCY-11"}})

    assert json.loads(correction.model_dump_json())["changes"] == {"scorerId": "HCY-11"}
    assert correction.model_dump()["changes"] == {"scorerId": "HCY-11"}
