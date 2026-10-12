"""The policy book: every partner's policy as Policy Studio edits it, versioned and audited.

An edit writes the partner's next version; nothing is overwritten, and every version keeps the
change that made it: who (the partner's duty editor, a named demo identity), when, why, and which
fields. The pipeline reads the current version at every item, so an edit governs the next item
without a restart. Who a policy belongs to (the partner, its locale, its duty editor) is set by
the studio and cannot be edited here.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from fourth_official_contracts import (
    PolicyChange,
    PolicyHistory,
    TenantId,
    TenantPolicy,
    parse_tenant_policy,
)
from fourth_official_policy.store import PolicyError, _explain, _parse

# Set by the studio: who the policy belongs to, not how it reads.
FIXED = ("tenantId", "locale", "dutyEditor")
# The fields a change can name, in the order a policy lists them.
EDITABLE = (
    "displayName",
    "tone",
    "preferTerms",
    "avoidTerms",
    "blockedTopics",
    "approvalRequired",
    "disclosureMode",
    "latencyBudgetMs",
    "maxItemsPerMinute",
    "templates",
    "correctionBehaviour",
)
BUNDLED_REASON = "Shipped with the release"


class StaleVersionError(PolicyError):
    """The edit was made on a version that is no longer current."""


class UnchangedPolicyError(PolicyError):
    """The edit changes nothing."""


class BookStore(Protocol):
    async def load(self) -> Mapping[str, PolicyHistory]: ...

    async def save(self, history: PolicyHistory) -> None: ...


class InMemoryBookStore:
    """For tests and local runs: kept for as long as the process lives."""

    def __init__(self) -> None:
        self._histories: dict[str, PolicyHistory] = {}

    async def load(self) -> Mapping[str, PolicyHistory]:
        return dict(self._histories)

    async def save(self, history: PolicyHistory) -> None:
        self._histories[history.tenant_id] = history


def _fields(before: TenantPolicy, after: TenantPolicy) -> tuple[Any, ...]:
    old, new = before.to_wire(), after.to_wire()
    return tuple(name for name in EDITABLE if old.get(name) != new.get(name))


class PolicyBook:
    def __init__(
        self,
        bundled: Sequence[TenantPolicy],
        store: BookStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._bundled = {p.tenant_id: p for p in bundled}
        self._store = store
        self._clock = clock
        self._histories: dict[str, PolicyHistory] = {}
        self._lock = asyncio.Lock()

    def _now(self) -> datetime:
        now = self._clock()
        return now.replace(microsecond=now.microsecond // 1000 * 1000)

    async def open(self) -> None:
        """Read the kept book; a partner it has never seen starts from the release's policy."""
        kept = await self._store.load()
        for tenant_id, policy in self._bundled.items():
            history = kept.get(tenant_id)
            if history is None:
                history = PolicyHistory(
                    tenant_id=tenant_id,
                    versions=(policy,),
                    changes=(self._change(policy, "bundled", BUNDLED_REASON, ()),),
                )
                await self._store.save(history)
            self._histories[tenant_id] = history

    def _change(
        self,
        policy: TenantPolicy,
        action: Literal["bundled", "edited", "reset"],
        reason: str,
        fields: tuple[Any, ...],
    ) -> PolicyChange:
        return PolicyChange(
            tenant_id=policy.tenant_id,
            version=policy.version,
            action=action,
            editor=policy.duty_editor,
            changed_at=self._now(),
            reason=reason,
            fields=fields,
        )

    def current(self, tenant_id: TenantId) -> TenantPolicy:
        return self._histories[tenant_id].current

    def history(self, tenant_id: TenantId) -> PolicyHistory:
        return self._histories[tenant_id]

    def version(self, tenant_id: TenantId, number: int) -> TenantPolicy:
        versions = self._histories[tenant_id].versions
        if not 1 <= number <= len(versions):
            raise KeyError(number)
        return versions[number - 1]

    def _proposed(self, current: TenantPolicy, proposed: Mapping[str, Any] | str) -> TenantPolicy:
        raw = _parse("The policy", proposed.encode()) if isinstance(proposed, str) else proposed
        if not isinstance(raw, Mapping):
            raise PolicyError("The policy must be a mapping of policy fields")
        wire = current.to_wire()
        fixed = [name for name in FIXED if name in raw and raw[name] != wire[name]]
        if fixed:
            raise PolicyError(f"{', '.join(fixed)} cannot be changed here: the studio sets them")
        try:
            return parse_tenant_policy(
                {**raw, **{n: wire[n] for n in FIXED}, "version": current.version + 1}
            )
        except ValidationError as error:
            raise _explain("The policy", error) from None

    async def _append(
        self, history: PolicyHistory, policy: TenantPolicy, change: PolicyChange
    ) -> None:
        updated = PolicyHistory(
            tenant_id=history.tenant_id,
            versions=(*history.versions, policy),
            changes=(*history.changes, change),
        )
        await self._store.save(updated)
        self._histories[history.tenant_id] = updated

    async def edit(
        self,
        tenant_id: TenantId,
        proposed: Mapping[str, Any] | str,
        *,
        base_version: int,
        reason: str,
    ) -> PolicyChange:
        """Write the partner's next version from a form's fields or raw YAML, made on
        `base_version`. Refused, with the reason in words, if it is not a valid policy."""
        async with self._lock:
            history = self._histories[tenant_id]
            current = history.current
            if base_version != current.version:
                raise StaleVersionError(
                    f"version {current.version} was written since version {base_version}"
                )
            policy = self._proposed(current, proposed)
            fields = _fields(current, policy)
            if not fields:
                raise UnchangedPolicyError("The edit changes nothing")
            try:
                change = self._change(policy, "edited", reason, fields)
            except ValidationError as error:
                raise _explain("The change", error) from None
            await self._append(history, policy, change)
            return change

    async def reset(self, *, reason: str) -> tuple[PolicyChange, ...]:
        """Every partner whose policy differs from the release's gets the release's back, as its
        next version."""
        async with self._lock:
            changes = []
            for tenant_id, bundled in self._bundled.items():
                history = self._histories[tenant_id]
                current = history.current
                policy = bundled.model_copy(update={"version": current.version + 1})
                fields = _fields(current, policy)
                if not fields:
                    continue
                change = self._change(policy, "reset", reason, fields)
                await self._append(history, policy, change)
                changes.append(change)
            return tuple(changes)
