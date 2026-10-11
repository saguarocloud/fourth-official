"""Record the featured match's feed (template explanations, no model) for the web app's tests:
the match feed alone, and the same match with every partner's items.

uv run python scripts/record-feed-fixture.py
(cd apps/web && npx prettier --write src/fixtures)   # the web app's format check covers them
"""

import asyncio
import json
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from fourth_official_contracts import (
    CorrectionReportEntry,
    FeedEntry,
    InsightEntry,
    Moment,
    TenantItemEntry,
)
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_policy import blocked_topics_in, bundled_store
from fourth_official_provenance import LocalSigner, record_for, sign_record
from fourth_official_replay import FeedLog, Partner, Partners, fixed_clocks, replay
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


async def main() -> None:
    await record("feed-m42.json", with_partners=False)
    await record("feed-m42-partners.json", with_partners=True)
    await record_provenance("provenance-m42.json")


if __name__ == "__main__":
    asyncio.run(main())
