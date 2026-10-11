"""Which items a named editor decides on before they air."""

from fourth_official_contracts import NARRATIVE_KINDS, ItemKind, TenantPolicy


def approval_required(policy: TenantPolicy, item_kind: ItemKind) -> bool:
    """Narrative items the policy routes to an editor. Data (stats, the score, corrections) never
    waits: a correction held for approval would leave a wrong fact on air."""
    return item_kind in NARRATIVE_KINDS and item_kind in policy.approval_required
