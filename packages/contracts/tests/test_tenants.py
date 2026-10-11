"""Tenant contracts: each broadcast partner's policy, the insight in its voice, the graphic that
carries it, and the feed entry that publishes it to that partner alone."""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import (
    LocalizedInsight,
    OverlaySpec,
    TenantItemEntry,
    parse_feed_entry,
    parse_localized_insight,
    parse_overlay_spec,
    parse_tenant_policy,
)
from test_insights import INSIGHT

POLICY: dict[str, Any] = {
    "tenantId": "rheinblick-sport",
    "version": 3,
    "displayName": "Rheinblick Sport",
    "locale": "de-DE",
    "tone": ["formal", "precise"],
    "preferTerms": ["Pressing", "Umschaltspiel"],
    "avoidTerms": ["Wahnsinn"],
    "blockedTopics": ["injury_speculation", "betting"],
    "approvalRequired": ["recap"],
    "disclosureMode": "eu-strict",
    "latencyBudgetMs": 8000,
    "maxItemsPerMinute": 4,
    "templates": ["lower_third", "stat_card", "correction_strap", "score_bug"],
    "correctionBehaviour": "auto-amend",
    "dutyEditor": "L. Vogt",
}

LOCALIZED: dict[str, Any] = {
    "itemId": "it-rheinblick-sport-in-m42-pressing_collapse-NGT-s1690-a1-v1",
    "tenantId": "rheinblick-sport",
    "locale": "de-DE",
    "insightId": INSIGHT["insightId"],
    "matchId": "m42",
    "momentId": INSIGHT["momentId"],
    "asOfSeq": INSIGHT["asOfSeq"],
    "version": 1,
    "headline": "{{club:NGT}} lassen im Pressing nach",
    "claims": [
        {
            **INSIGHT["claims"][0],
            "text": "{{club:NGT}} pressen jetzt {{value:"
            + INSIGHT["claims"][0]["evidence"]["metricSnapshotIds"][1]
            + "}} Mal pro Ballkontakt.",
        },
    ],
    "provenance": {
        "agent": "localizer",
        "promptVersion": "v1.0",
        "model": "fast",
        "producedBy": "model",
    },
    "policyVersion": 3,
}

CLOCK = {"period": 2, "minute": 61, "second": 5}
LATER = {"period": 2, "minute": 61, "second": 13}

OVERLAY: dict[str, Any] = {
    "itemId": LOCALIZED["itemId"],
    "tenantId": "rheinblick-sport",
    "locale": "de-DE",
    "inAt": CLOCK,
    "outAt": LATER,
    "priority": 2,
    "content": {
        "template": "lower_third",
        "headline": "Northgate FC lassen im Pressing nach",
        "line": "Northgate FC pressen jetzt 0,28 Mal pro Ballkontakt.",
    },
    "disclosure": {"label": "KI-generiert", "mode": "eu-strict", "reason": "ai_generated"},
    "provenanceUrl": None,
    "version": 1,
    "supersedes": None,
}

TENANT_ITEM: dict[str, Any] = {
    "kind": "tenant_item",
    "entrySeq": 9,
    "matchId": "m42",
    "tenantId": "rheinblick-sport",
    "itemKind": "insight",
    "state": "on_air",
    "localized": LOCALIZED,
    "rendered": {
        "headline": OVERLAY["content"]["headline"],
        "claims": [OVERLAY["content"]["line"]],
    },
    "overlay": OVERLAY,
    "approvalRequired": False,
    "attempts": [
        {
            "number": 1,
            "agent": "localizer",
            "model": "fast",
            "outcome": "passed",
            "findings": [],
            "error": None,
        }
    ],
    "approval": None,
}


def changed(base: dict[str, Any], path: tuple[str, ...], value: object) -> dict[str, Any]:
    data = copy.deepcopy(base)
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


# --- Tenant policy ----------------------------------------------------------------------------


def test_a_policy_round_trips_on_the_wire() -> None:
    policy = parse_tenant_policy(POLICY)

    assert policy.tenant_id == "rheinblick-sport"
    assert policy.to_wire() == POLICY


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("tenantId",), "evil-sport"),
        (("locale",), "fr-FR"),
        (("disclosureMode",), "label-sometimes"),
        (("blockedTopics",), ["weather"]),
        (("templates",), []),
        (("latencyBudgetMs",), 50),
        (("maxItemsPerMinute",), 0),
        (("version",), 0),
        (("preferTerms",), ["Pressing", "Pressing"]),
        (("avoidTerms",), ["Pressing"]),
        (("tone",), ["x" * 41]),
        (("approvalRequired",), ["insight", "insight"]),
    ],
)
def test_an_invalid_policy_is_refused(path: tuple[str, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        parse_tenant_policy(changed(POLICY, path, value))


def test_a_policy_names_unknown_fields_rather_than_ignoring_them() -> None:
    with pytest.raises(ValidationError, match="extra"):
        parse_tenant_policy({**POLICY, "autoPublishEverything": True})


# --- Localised insight ------------------------------------------------------------------------


def test_a_localised_insight_round_trips_and_keeps_its_source() -> None:
    localized = parse_localized_insight(LOCALIZED)

    assert localized.insight_id == INSIGHT["insightId"]
    assert localized.to_wire() == LOCALIZED


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("momentId",), "mo-m43-goal-KBA-s0101"),
        (("matchId",), "m43"),
        (("itemId",), "it-northlight-sport-x"),
        (("locale",), "en"),
        (("claims",), []),
    ],
)
def test_an_inconsistent_localised_insight_is_refused(path: tuple[str, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        parse_localized_insight(changed(LOCALIZED, path, value))


def test_a_localised_claim_keeps_the_contract_on_its_markup() -> None:
    broken = changed(LOCALIZED, ("claims",), [{**LOCALIZED["claims"][0], "text": "{{club:ngt}}"}])

    with pytest.raises(ValidationError, match="markup"):
        parse_localized_insight(broken)


# --- Overlay spec -----------------------------------------------------------------------------


def test_an_overlay_round_trips() -> None:
    overlay = parse_overlay_spec(OVERLAY)

    assert isinstance(overlay, OverlaySpec)
    assert overlay.to_wire() == OVERLAY


@pytest.mark.parametrize(
    "content",
    [
        {
            "template": "stat_card",
            "title": "Pressing",
            "rows": [{"label": "Jetzt", "value": "0,28"}],
        },
        {"template": "correction_strap", "text": "KORREKTUR: Tor in der 67. Minute aberkannt"},
        {"template": "score_bug", "home": "HCY", "away": "NGT", "score": "2:1", "clock": "93:00"},
    ],
)
def test_every_template_has_its_own_content(content: dict[str, Any]) -> None:
    assert (
        parse_overlay_spec({**OVERLAY, "content": content}).content.template == content["template"]
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("outAt",), CLOCK),
        (("outAt",), {"period": 1, "minute": 70, "second": 0}),
        (("content", "rows"), []),
        (("content", "template"), "fireworks"),
        (("priority",), 10),
        (("provenanceUrl",), "javascript:alert(1)"),
        (("supersedes",), OVERLAY["itemId"]),
    ],
)
def test_an_invalid_overlay_is_refused(path: tuple[str, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        parse_overlay_spec(changed(OVERLAY, path, value))


def test_overlay_text_is_one_short_printable_line() -> None:
    with pytest.raises(ValidationError):
        parse_overlay_spec(changed(OVERLAY, ("content", "headline"), "Tor" + chr(0x202E) + "!"))
    with pytest.raises(ValidationError):
        parse_overlay_spec(changed(OVERLAY, ("content", "headline"), "x" * 121))


# --- Tenant feed entry ------------------------------------------------------------------------


def test_a_tenant_item_is_a_feed_entry() -> None:
    entry = parse_feed_entry(TENANT_ITEM)

    assert isinstance(entry, TenantItemEntry)
    assert entry.to_wire() == TENANT_ITEM


@pytest.mark.parametrize(
    ("path", "value"),
    [
        # Another tenant's graphic, or another tenant's words, never ride on this entry.
        (("overlay", "tenantId"), "northlight-sport"),
        (("localized", "tenantId"), "tribuna-austral"),
        (("matchId",), "m43"),
        # A narrative item carries the words it puts on air.
        (("localized",), None),
        (("rendered",), None),
        (("attempts",), []),
        # Only an item on air has been approved; a pending one has not.
        (("state",), "pending_approval"),
    ],
)
def test_an_inconsistent_tenant_item_is_refused(path: tuple[str, ...], value: object) -> None:
    data = changed(TENANT_ITEM, path, value)
    if path == ("state",):
        data["approval"] = {
            "editor": "T. Ibarra",
            "decidedAt": "2026-10-11T15:00:00Z",
            "decision": "approved",
        }

    with pytest.raises(ValidationError):
        parse_feed_entry(data)


def test_a_data_item_needs_no_words_or_attempts() -> None:
    strap = {
        **TENANT_ITEM,
        "itemKind": "correction",
        "localized": None,
        "rendered": None,
        "attempts": [],
        "overlay": {
            **OVERLAY,
            "content": {"template": "correction_strap", "text": "KORREKTUR: Tor aberkannt"},
            "disclosure": None,
        },
    }

    assert parse_feed_entry(strap).item_kind == "correction"  # type: ignore[union-attr]


def test_a_localised_insight_type_is_exported() -> None:
    assert LocalizedInsight.__name__ == "LocalizedInsight"


# --- Review hardening -------------------------------------------------------------------------

SCORE_BUG = {
    "template": "score_bug",
    "home": "HCY",
    "away": "NGT",
    "score": "2:1",
    "clock": "61:05",
}
APPROVED = {"editor": "T. Ibarra", "decidedAt": "2026-10-11T15:00:00Z", "decision": "approved"}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("locale",), "es-MX"),
        (("displayName",), "Rhein\nblick"),
        (("displayName",), "Rhein" + chr(0x202E)),
        (("templates",), ["lower_third", "stat_card", "score_bug"]),
        (("approvalRequired",), ["stat"]),
    ],
)
def test_a_policy_keeps_its_partner_s_locale_safe_text_and_needed_templates(
    path: tuple[str, ...], value: object
) -> None:
    data = changed(POLICY, path, value)
    if path == ("approvalRequired",):
        data["templates"] = ["lower_third", "correction_strap"]

    with pytest.raises(ValidationError):
        parse_tenant_policy(data)


def test_terms_are_compared_as_text_not_code_points() -> None:
    decomposed = "Cafe" + chr(0x0301)

    with pytest.raises(ValidationError, match="both preferred and avoided"):
        parse_tenant_policy({**POLICY, "preferTerms": [decomposed], "avoidTerms": ["Café"]})


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("locale",), "es-MX"),
        (("inAt",), {"period": 1, "minute": 45, "second": 50}),
        (("outAt",), {"period": 2, "minute": 62, "second": 30}),
        (("provenanceUrl",), "https://user:pw@evil.example/item"),
        (("provenanceUrl",), "https://verify.example/" + chr(0x202E)),
        (("supersedes",), "it-northlight-sport-in-m42-goal-HCY-s0004-a1-v1"),
        (("disclosure", "label"), "KI\ngeneriert"),
    ],
)
def test_an_overlay_stays_with_its_partner_and_on_screen_briefly(
    path: tuple[str, ...], value: object
) -> None:
    with pytest.raises(ValidationError):
        parse_overlay_spec(changed(OVERLAY, path, value))


def test_an_overlay_may_supersede_an_earlier_version_of_the_partner_s_own_item() -> None:
    data = {**OVERLAY, "version": 2, "supersedes": "it-rheinblick-sport-in-m42-x-v1"}

    assert parse_overlay_spec(data).supersedes == "it-rheinblick-sport-in-m42-x-v1"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        # The words, the graphic and the partner speak one language.
        (("overlay", "locale"), "es-MX"),
        # The graphic shows exactly the words rendered for the item.
        (("overlay", "content", "headline"), "Something else"),
        (("rendered", "headline"), "Something else"),
        # Each kind of item has its own graphic.
        (("overlay", "content"), SCORE_BUG),
        # An AI-written item is always disclosed, with a label when the mode asks for one.
        (("overlay", "disclosure"), None),
        (("overlay", "disclosure", "label"), None),
        (("overlay", "disclosure", "reason"), "data"),
        (("overlay", "disclosure", "reason"), "ai_assisted_reviewed"),
    ],
)  # fmt: skip
def test_a_tenant_item_is_one_partner_s_one_graphic_honestly_labelled(
    path: tuple[str, ...], value: object
) -> None:
    with pytest.raises(ValidationError):
        parse_feed_entry(changed(TENANT_ITEM, path, value))


def approval_case(state: str, required: bool, approval: dict[str, Any] | None) -> dict[str, Any]:
    data = {**TENANT_ITEM, "state": state, "approvalRequired": required, "approval": approval}
    if approval is not None and approval["decision"] == "approved":
        data = changed(data, ("overlay", "disclosure", "reason"), "ai_assisted_reviewed")
        data = changed(
            data, ("overlay", "disclosure", "label"), "KI-gestützt · Geprüft von T. Ibarra"
        )
    return data


@pytest.mark.parametrize(
    ("state", "required", "approval", "valid"),
    [
        ("on_air", False, None, True),
        ("on_air", True, None, False),
        ("on_air", True, APPROVED, True),
        ("pending_approval", True, None, True),
        ("pending_approval", False, None, False),
        ("pending_approval", True, APPROVED, False),
        ("rejected", True, {**APPROVED, "decision": "rejected", "reason": "Off tone"}, True),
        ("rejected", True, None, False),
        ("on_air", True, {**APPROVED, "decision": "rejected", "reason": "Off tone"}, False),
    ],
)
def test_approval_and_state_agree(
    state: str, required: bool, approval: dict[str, Any] | None, valid: bool
) -> None:
    data = approval_case(state, required, approval)

    if valid:
        assert parse_feed_entry(data).state == state  # type: ignore[union-attr]
    else:
        with pytest.raises(ValidationError):
            parse_feed_entry(data)


def test_a_reviewed_label_needs_the_approval_behind_it() -> None:
    data = changed(TENANT_ITEM, ("overlay", "disclosure", "reason"), "ai_assisted_reviewed")

    with pytest.raises(ValidationError):
        parse_feed_entry(data)


# --- Editors' decisions ------------------------------------------------------------------------


def test_a_policy_names_its_duty_editor() -> None:
    assert parse_tenant_policy(POLICY).duty_editor == "L. Vogt"
    with pytest.raises(ValidationError):
        parse_tenant_policy({**POLICY, "dutyEditor": "nobody<script>"})


def test_an_approval_carries_no_reason() -> None:
    with pytest.raises(ValidationError):
        parse_feed_entry(approval_case("on_air", True, {**APPROVED, "reason": "Fine"}))


def test_a_rejection_says_why() -> None:
    rejected = {**APPROVED, "decision": "rejected", "reason": "Wrong tone for our audience"}

    assert parse_feed_entry(approval_case("rejected", True, rejected)).approval.reason == (  # type: ignore[union-attr]
        "Wrong tone for our audience"
    )


@pytest.mark.parametrize(
    "reason",
    [None, "", "   ", "two\nlines", "x" * 201],
)
def test_a_rejection_without_one_clear_reason_is_refused(reason: str | None) -> None:
    rejected = {**APPROVED, "decision": "rejected", "reason": reason}

    with pytest.raises(ValidationError):
        parse_feed_entry(approval_case("rejected", True, rejected))
