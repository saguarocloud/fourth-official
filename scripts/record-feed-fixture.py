"""Record the featured match's feed (template explanations, no model) for the web app's tests:
the match feed alone, and the same match with every partner's items; and a matchday's operations
report, from replays timed by a fixed clock with synthetic model attempts and tokens.

uv run python scripts/record-feed-fixture.py
(cd apps/web && npx prettier --write src/fixtures)   # the web app's format check covers them
"""

import asyncio
import dataclasses
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import partial
from itertools import count
from pathlib import Path

from fourth_official_contracts import (
    CorrectionReportEntry,
    FeedEntry,
    InsightEntry,
    Moment,
    Provenance,
    TenantItemEntry,
)
from fourth_official_explain import Explanation, explain
from fourth_official_explain.localize import LocalizationRequest, LocalizedDraft
from fourth_official_explain.metering import TokenCount, spend
from fourth_official_explain.pipeline import Attempt
from fourth_official_match_data import demo_store
from fourth_official_policy import blocked_topics_in, bundled_store
from fourth_official_policy.book import InMemoryBookStore, PolicyBook
from fourth_official_provenance import LocalSigner, record_for, sign_record
from fourth_official_replay import FeedLog, Partner, Partners, fixed_clocks, replay
from fourth_official_replay.operations import measure, report
from fourth_official_verifier import MatchFacts

FIXTURES = Path(__file__).resolve().parents[1] / "apps/web/src/fixtures"


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


async def no_wait(seconds: float) -> None:
    return None


def partners() -> Partners:
    return Partners(
        [
            Partner(policy=p.policy, blocked=partial(blocked_topics_in, policy=p.policy))
            for p in bundled_store().all()
        ],
        localizer=None,
    )


async def record(name: str, *, with_partners: bool) -> None:
    log = FeedLog("m42")
    await replay(
        demo_store().record("m42"),
        log,
        template_only,
        sleep=no_wait,
        partners=partners() if with_partners else None,
        clocks=fixed_clocks(),
    )
    entries = [entry.to_wire() for entry in log.entries]
    out = FIXTURES / name
    out.write_text(json.dumps(entries, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} entries to {out}")


# The records the web app's Provenance tests read: one item in each state worth showing.
FIXTURE_TIME = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)


def _latest(entries: list[FeedEntry]) -> dict[str, TenantItemEntry]:
    latest: dict[str, TenantItemEntry] = {}
    for entry in entries:
        if isinstance(entry, TenantItemEntry) and entry.localized is not None:
            latest[entry.overlay.item_id] = entry
    return latest


async def record_provenance(name: str) -> None:
    log = FeedLog("m42")
    await replay(
        demo_store().record("m42"),
        log,
        template_only,
        sleep=no_wait,
        partners=partners(),
        clocks=fixed_clocks(),
    )
    entries = list(log.entries)
    latest = _latest(entries)
    chosen = [
        next(
            i for i in latest.values() if i.tenant_id == "northlight-sport" and i.state == "on_air"
        ),
        next(i for i in latest.values() if i.state == "pending_approval"),
        next(i for i in latest.values() if i.state == "retracted"),
        next(i for i in latest.values() if i.overlay.supersedes is not None),
    ]
    signer = LocalSigner(b"fixture-signing-key-not-a-secret!", key_id="local:fixture")
    answers = {}
    for item in chosen:
        canonical = next(
            e
            for e in entries
            if isinstance(e, InsightEntry)
            and item.localized is not None
            and e.insight.insight_id == item.localized.insight_id
        )
        corrections = sorted(
            {
                e.correction_id
                for e in entries
                if isinstance(e, CorrectionReportEntry)
                and any(a.item_id == item.overlay.item_id for a in e.actions)
            }
        )
        record = record_for(item, canonical, issued_at=FIXTURE_TIME, corrections=corrections)
        if record is None:
            raise SystemExit(f"no record for {item.overlay.item_id}")
        signed = await sign_record(record, signer)
        answers[item.overlay.item_id] = {
            "provenance": signed.to_wire(),
            "verification": {"valid": True, "reason": None},
        }
    out = FIXTURES / name
    out.write_text(json.dumps(answers, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(answers)} records to {out}")


async def record_policy_history(name: str) -> None:
    """Rheinblick's policy history as Policy Studio would leave it: the release's version, an edit,
    and a reset."""
    # Five minutes later at every stamp, so each change has its own time.
    clock = (datetime(2026, 10, 12, 9, 0, tzinfo=UTC) + timedelta(minutes=5 * n) for n in count())
    book = PolicyBook(
        [loaded.policy for loaded in bundled_store().all()],
        InMemoryBookStore(),
        clock=lambda: next(clock),
    )
    await book.open()
    first = book.current("rheinblick-sport")
    edited = first.to_wire() | {
        "approvalRequired": ["recap", "insight"],
        "maxItemsPerMinute": 3,
        "avoidTerms": ["Wahnsinn", "Skandal"],
    }
    await book.edit(
        "rheinblick-sport", edited, base_version=1, reason="Hold insights for the duty editor"
    )
    await book.reset(reason="Back to the release after the review")
    out = FIXTURES / name
    history = book.history("rheinblick-sport").to_wire()
    out.write_text(json.dumps(history, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(history['versions'])} versions to {out}")


# The recorded run: a reading of the log's clock every 6 ms of synthetic time.
TICK_SECONDS = 0.006
# Moments explained so far in the recording, so every third one falls back.
_EXPLAINED = count()


def ticking() -> Callable[[], float]:
    readings = count()
    return lambda: next(readings) * TICK_SECONDS


async def drafted(moment: Moment, facts: MatchFacts) -> Explanation:
    """The template's insight, as if the models had drafted it: most moments pass on the fast
    model's first draft; every third falls back after a timeout and a refused draft. Synthetic,
    so the screen has model attempts and tokens to show."""
    explanation = await explain(moment, facts, [])
    template = explanation.attempts[-1]
    tokens = 2400 + moment.as_of_seq % 900
    if next(_EXPLAINED) % 3 == 2:
        tried = (
            Attempt(1, "analyst", "fast", "error", error="TimeoutError", input_tokens=tokens),
            Attempt(2, "analyst", "fallback", "failed", ("BARE_NUMBER",), None, tokens, 310),
        )
        return dataclasses.replace(
            explanation, attempts=(*tried, dataclasses.replace(template, number=3))
        )
    passed = Attempt(1, "analyst", "fast", "passed", (), None, tokens, 260)
    return dataclasses.replace(explanation, attempts=(passed,))


class Spending:
    """A Localizer that spends tokens and fails, so each partner's template stands in."""

    provenance = Provenance(
        agent="localizer", prompt_version="v1.0", model="fast", produced_by="model"
    )

    async def draft(self, request: LocalizationRequest) -> LocalizedDraft:
        spend(TokenCount(model="fast", input=900, output=140))
        raise TimeoutError


async def record_operations(name: str) -> None:
    store = demo_store()
    measured = []
    matches = store.match_ids()
    for match_id in matches:
        log = FeedLog(match_id, clock=ticking())
        await log.reset()
        localizing = Partners(
            [
                Partner(policy=p.policy, blocked=partial(blocked_topics_in, policy=p.policy))
                for p in bundled_store().all()
            ],
            localizer=Spending(),
        )
        await replay(
            store.record(match_id),
            log,
            drafted,
            sleep=no_wait,
            partners=localizing,
            clocks=fixed_clocks(),
        )
        budgets = {p.policy.tenant_id: p.policy.latency_budget_ms for p in bundled_store().all()}
        entries, timing = log.snapshot()
        measured.append(
            measure(
                match_id,
                "finished",
                entries,
                timing,
                now=log.now(),
                sharing=len(matches),
                budgets=budgets,
            )
        )
    out = FIXTURES / name
    wire = report(measured, generated_at=FIXTURE_TIME).to_wire()
    out.write_text(json.dumps(wire, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote operations for {len(measured)} matches to {out}")


async def main() -> None:
    await record("feed-m42.json", with_partners=False)
    await record("feed-m42-partners.json", with_partners=True)
    await record_provenance("provenance-m42.json")
    await record_policy_history("policy-history-rheinblick.json")
    await record_operations("operations.json")


if __name__ == "__main__":
    asyncio.run(main())
