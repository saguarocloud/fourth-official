"""Approval routing: which items a named editor decides on before they air, per partner."""

import pytest

from fourth_official_contracts import ItemKind, TenantId
from fourth_official_policy import approval_required, bundled_store


@pytest.mark.parametrize(
    ("tenant", "kind", "required"),
    [
        ("northlight-sport", "insight", False),
        ("northlight-sport", "recap", True),
        ("tribuna-austral", "insight", True),
        ("tribuna-austral", "stat", False),
        ("rheinblick-sport", "insight", False),
        ("rheinblick-sport", "recap", True),
        # Data never waits for an editor, whatever a policy says.
        ("tribuna-austral", "correction", False),
        ("tribuna-austral", "score", False),
    ],
)
def test_each_partner_routes_its_items(tenant: TenantId, kind: ItemKind, required: bool) -> None:
    assert approval_required(bundled_store().get(tenant).policy, kind) is required
