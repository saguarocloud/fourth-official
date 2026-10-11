"""An editor's decision on a held item: approved, it goes on air from the match clock with the
editor's name in its label where the policy says so; rejected, it stays off air with the reason."""

from datetime import UTC, datetime

import anyio
import pytest

from fourth_official_contracts import MatchClock, TenantItemEntry, parse_feed_entry
from fourth_official_replay.errors import DecisionError
from test_partners import of, partners

NOW = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)
AT = MatchClock(period=2, minute=70, second=0)


def decide(item: TenantItemEntry, decision: str, reason: str | None = None) -> TenantItemEntry:
    async def run() -> TenantItemEntry:
        build = await partners().decide(item, decision, reason=reason, at=AT, now=NOW)  # type: ignore[arg-type]
        return build(500)

    return anyio.run(run)


def held() -> TenantItemEntry:
    return of("tribuna-austral", "insight")[0]


def test_an_approved_item_goes_on_air_from_the_match_clock_signed_by_its_editor() -> None:
    item = held()

    entry = decide(item, "approved")

    assert entry.state == "on_air"
    assert entry.approval is not None
    assert (entry.approval.editor, entry.approval.decision) == ("T. Ibarra", "approved")
    assert entry.approval.decided_at == NOW
    assert entry.overlay.disclosure is not None
    assert entry.overlay.disclosure.label == "Asistido por IA · Revisado por T. Ibarra"
    assert entry.overlay.in_at == AT
    assert entry.overlay.item_id == item.overlay.item_id
    assert (entry.localized, entry.rendered, entry.attempts) == (
        item.localized,
        item.rendered,
        item.attempts,
    )
    assert entry.entry_seq == 500
    assert parse_feed_entry(entry.to_wire()) == entry


def test_a_rejected_item_stays_off_air_with_the_reason() -> None:
    item = held()

    entry = decide(item, "rejected", "Not our tone")

    assert entry.state == "rejected"
    assert entry.approval is not None
    assert (entry.approval.decision, entry.approval.reason) == ("rejected", "Not our tone")
    assert entry.overlay == item.overlay


def test_a_partner_that_shows_no_label_on_reviewed_items_drops_it() -> None:
    item = of("northlight-sport", "insight")[0]
    pending = item.model_copy(
        update={"state": "pending_approval", "approval_required": True, "approval": None}
    )

    entry = decide(pending, "approved")

    assert entry.overlay.disclosure is not None
    assert entry.overlay.disclosure.label is None
    assert entry.approval is not None
    assert entry.approval.editor == "R. Hale"


@pytest.mark.parametrize("decided", ["approved", "rejected"])
def test_only_an_item_awaiting_a_decision_can_be_decided(decided: str) -> None:
    on_air = of("rheinblick-sport", "insight")[0]

    with pytest.raises(DecisionError, match="not awaiting"):
        decide(on_air, decided, "Not our tone" if decided == "rejected" else None)


def test_a_rejection_needs_its_reason() -> None:
    with pytest.raises(DecisionError, match="reason"):
        decide(held(), "rejected", "   ")
