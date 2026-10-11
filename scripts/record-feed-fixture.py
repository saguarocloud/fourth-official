"""Record the featured match's feed (template explanations, no model) for the web app's tests:
the match feed alone, and the same match with every partner's items.

uv run python scripts/record-feed-fixture.py
(cd apps/web && npx prettier --write src/fixtures)   # the web app's format check covers them
"""

import asyncio
import json
from functools import partial
from pathlib import Path

from fourth_official_contracts import Moment
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_policy import blocked_topics_in, bundled_store
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


async def main() -> None:
    await record("feed-m42.json", with_partners=False)
    await record("feed-m42-partners.json", with_partners=True)


if __name__ == "__main__":
    asyncio.run(main())
