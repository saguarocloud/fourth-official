"""The policy book: partners' policies as Policy Studio edits them, versioned and audited."""

from datetime import UTC, datetime

import anyio
import pytest

from fourth_official_contracts import PolicyHistory, TenantId
from fourth_official_policy import bundled_store
from fourth_official_policy.book import (
    InMemoryBookStore,
    PolicyBook,
    StaleVersionError,
    UnchangedPolicyError,
)
from fourth_official_policy.store import PolicyError

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
RHEINBLICK: TenantId = "rheinblick-sport"
BUNDLED = {loaded.policy.tenant_id: loaded.policy for loaded in bundled_store().all()}


def book(store: InMemoryBookStore | None = None) -> PolicyBook:
    opened = PolicyBook(
        [loaded.policy for loaded in bundled_store().all()],
        store or InMemoryBookStore(),
        clock=lambda: NOW,
    )
    anyio.run(opened.open)
    return opened


def edited(**changes: object) -> dict[str, object]:
    """Rheinblick's released policy with some fields changed, as a form would send it."""
    return BUNDLED[RHEINBLICK].to_wire() | changes


def test_a_new_book_starts_from_the_release_s_policies() -> None:
    opened = book()

    for loaded in bundled_store().all():
        assert opened.current(loaded.policy.tenant_id) == loaded.policy
        (first,) = opened.history(loaded.policy.tenant_id).changes
        assert (first.action, first.version, first.fields) == ("bundled", 1, ())


def test_an_edit_is_the_next_version_with_who_what_and_why() -> None:
    opened = book()
    proposed = edited(approvalRequired=["recap", "insight"], maxItemsPerMinute=3)

    change = anyio.run(
        lambda: opened.edit(RHEINBLICK, proposed, base_version=1, reason="Review every insight")
    )

    assert change.version == 2
    assert change.action == "edited"
    assert change.editor == "L. Vogt"
    assert change.changed_at == NOW
    assert change.fields == ("approvalRequired", "maxItemsPerMinute")
    assert opened.current(RHEINBLICK).approval_required == ("recap", "insight")
    assert opened.version(RHEINBLICK, 1).approval_required == ("recap",)


def test_raw_yaml_is_read_strictly_like_a_policy_file() -> None:
    opened = book()
    text = (
        "\n".join(
            f"{key}: {value}"
            for key, value in {
                "tenantId": "rheinblick-sport",
                "version": 1,
                "displayName": "Rheinblick Sport",
                "locale": "de-DE",
                "tone": "[formal, precise]",
                "preferTerms": "[Pressing, Umschaltspiel, Torchance]",
                "avoidTerms": "[Wahnsinn]",
                "blockedTopics": "[injury_speculation, betting, transfer_rumour, off_field]",
                "approvalRequired": "[recap]",
                "disclosureMode": "eu-strict",
                "latencyBudgetMs": 6000,
                "maxItemsPerMinute": 4,
                "templates": "[lower_third, stat_card, correction_strap, score_bug]",
                "correctionBehaviour": "auto-amend",
                "dutyEditor": "L. Vogt",
            }.items()
        )
        + "\n"
    )

    change = anyio.run(
        lambda: opened.edit(RHEINBLICK, text, base_version=1, reason="Tighter budget")
    )

    assert change.fields == ("latencyBudgetMs",)
    with pytest.raises(PolicyError, match="repeats the key"):
        anyio.run(
            lambda: opened.edit(RHEINBLICK, text + "tone: [loud]\n", base_version=2, reason="Twice")
        )


@pytest.mark.parametrize(
    ("changes", "explained"),
    [
        ({"maxItemsPerMinute": 99}, "maxItemsPerMinute: Input should be less than or equal to 30"),
        ({"templates": ["lower_third", "score_bug"]}, "correction_strap is required"),
        ({"preferTerms": ["Wahnsinn"]}, "both preferred and avoided"),
        ({"disclosureMode": "never"}, "disclosureMode"),
    ],
)
def test_an_invalid_policy_is_refused_in_words(changes: dict[str, object], explained: str) -> None:
    opened = book()

    with pytest.raises(PolicyError, match=explained):
        anyio.run(lambda: opened.edit(RHEINBLICK, edited(**changes), base_version=1, reason="x"))
    assert opened.current(RHEINBLICK).version == 1


@pytest.mark.parametrize(
    "changes",
    [{"tenantId": "northlight-sport"}, {"locale": "en-GB"}, {"dutyEditor": "Someone Else"}],
)
def test_who_a_policy_belongs_to_is_not_editable(changes: dict[str, object]) -> None:
    opened = book()
    with pytest.raises(PolicyError, match="cannot be changed here"):
        anyio.run(lambda: opened.edit(RHEINBLICK, edited(**changes), base_version=1, reason="x"))


def test_an_edit_made_on_an_old_version_is_refused() -> None:
    opened = book()
    anyio.run(
        lambda: opened.edit(RHEINBLICK, edited(latencyBudgetMs=6000), base_version=1, reason="a")
    )

    with pytest.raises(StaleVersionError):
        anyio.run(
            lambda: opened.edit(
                RHEINBLICK, edited(latencyBudgetMs=7000), base_version=1, reason="b"
            )
        )


def test_an_edit_that_changes_nothing_is_refused() -> None:
    opened = book()
    with pytest.raises(UnchangedPolicyError):
        anyio.run(lambda: opened.edit(RHEINBLICK, edited(), base_version=1, reason="nothing"))


def test_reset_brings_back_the_release_s_policies_as_new_versions() -> None:
    opened = book()
    anyio.run(
        lambda: opened.edit(RHEINBLICK, edited(maxItemsPerMinute=2), base_version=1, reason="a")
    )

    changes = anyio.run(lambda: opened.reset(reason="Back to the release"))

    (reset,) = changes
    assert (reset.tenant_id, reset.version, reset.action) == (RHEINBLICK, 3, "reset")
    assert reset.fields == ("maxItemsPerMinute",)
    assert opened.current(RHEINBLICK).max_items_per_minute == 4


def test_the_book_is_kept_and_read_back() -> None:
    store = InMemoryBookStore()
    first = book(store)
    anyio.run(
        lambda: first.edit(RHEINBLICK, edited(maxItemsPerMinute=2), base_version=1, reason="a")
    )

    again = book(store)

    assert again.current(RHEINBLICK).max_items_per_minute == 2
    assert isinstance(again.history(RHEINBLICK), PolicyHistory)
    assert [c.version for c in again.history(RHEINBLICK).changes] == [1, 2]
