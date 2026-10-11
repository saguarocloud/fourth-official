"""What a partner's audience is told about AI involvement. Labels come from this table, in the
partner's language, never from a model."""

from fourth_official_contracts import (
    NARRATIVE_KINDS,
    Approval,
    Disclosure,
    ItemKind,
    Locale,
    TenantPolicy,
)

GENERATED: dict[Locale, str] = {
    "en-GB": "AI-generated",
    "es-MX": "Generado con IA",
    "de-DE": "KI-generiert",
}
REVIEWED: dict[Locale, str] = {
    "en-GB": "AI-assisted · Reviewed by {editor}",
    "es-MX": "Asistido por IA · Revisado por {editor}",
    "de-DE": "KI-gestützt · Geprüft von {editor}",
}


def disclose(
    policy: TenantPolicy, item_kind: ItemKind, approval: Approval | None
) -> Disclosure | None:
    """The disclosure for an item, or None for data, which no agent wrote.

    - Not reviewed: labelled as AI-generated in every mode.
    - Reviewed under `label-unless-approved`: no label.
    - Reviewed under `label-all` or `eu-strict`: labelled as AI-assisted, naming the editor.
    """
    if item_kind not in NARRATIVE_KINDS:
        return None
    mode = policy.disclosure_mode
    if approval is None or approval.decision != "approved":
        return Disclosure(label=GENERATED[policy.locale], mode=mode, reason="ai_generated")
    if mode == "label-unless-approved":
        return Disclosure(label=None, mode=mode, reason="ai_assisted_reviewed")
    label = REVIEWED[policy.locale].format(editor=approval.editor)
    return Disclosure(label=label, mode=mode, reason="ai_assisted_reviewed")
