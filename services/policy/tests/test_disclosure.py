"""Disclosure: what each partner's audience is told about AI involvement, in its own language."""

from datetime import UTC, datetime

import pytest

from fourth_official_contracts import Approval, TenantId, TenantPolicy
from fourth_official_policy import bundled_store, disclose

APPROVED = Approval(
    editor="T. Ibarra", decided_at=datetime(2026, 10, 11, tzinfo=UTC), decision="approved"
)


def policy(tenant: TenantId) -> TenantPolicy:
    return bundled_store().get(tenant).policy


@pytest.mark.parametrize("kind", ["stat", "correction", "score"])
def test_data_items_carry_no_ai_label(kind: str) -> None:
    for tenant in ("northlight-sport", "tribuna-austral", "rheinblick-sport"):
        assert disclose(policy(tenant), kind, None) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tenant", "label"),
    [
        ("northlight-sport", "AI-generated"),
        ("tribuna-austral", "Generado con IA"),
        ("rheinblick-sport", "KI-generiert"),
    ],
)
def test_unreviewed_narrative_is_labelled_in_the_partner_s_language(
    tenant: TenantId, label: str
) -> None:
    disclosure = disclose(policy(tenant), "insight", None)

    assert disclosure is not None
    assert (disclosure.label, disclosure.reason) == (label, "ai_generated")
    assert disclosure.mode == policy(tenant).disclosure_mode


def test_label_unless_approved_drops_the_label_once_an_editor_approves() -> None:
    disclosure = disclose(policy("northlight-sport"), "insight", APPROVED)

    assert disclosure is not None
    assert (disclosure.label, disclosure.reason) == (None, "ai_assisted_reviewed")


@pytest.mark.parametrize(
    ("tenant", "label"),
    [
        ("tribuna-austral", "Asistido por IA · Revisado por T. Ibarra"),
        ("rheinblick-sport", "KI-gestützt · Geprüft von T. Ibarra"),
    ],
)
def test_strict_modes_name_the_reviewing_editor(tenant: TenantId, label: str) -> None:
    disclosure = disclose(policy(tenant), "insight", APPROVED)

    assert disclosure is not None
    assert (disclosure.label, disclosure.reason) == (label, "ai_assisted_reviewed")


def test_a_rejection_is_not_a_review() -> None:
    rejected = APPROVED.model_copy(update={"decision": "rejected"})

    disclosure = disclose(policy("rheinblick-sport"), "insight", rejected)

    assert disclosure is not None
    assert disclosure.reason == "ai_generated"
