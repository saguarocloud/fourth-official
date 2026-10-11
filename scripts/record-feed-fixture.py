"""Record the featured match's feed (template explanations, no model) for the web app's tests.

uv run python scripts/record-feed-fixture.py
"""

import asyncio
import json
from pathlib import Path

from fourth_official_contracts import Moment
from fourth_official_explain import Explanation, explain
from fourth_official_match_data import demo_store
from fourth_official_replay import FeedLog, replay
from fourth_official_verifier import MatchFacts

OUT = Path(__file__).resolve().parents[1] / "apps/web/src/fixtures/feed-m42.json"


async def template_only(moment: Moment, facts: MatchFacts) -> Explanation:
    return await explain(moment, facts, [])


async def no_wait(seconds: float) -> None:
    return None


async def main() -> None:
    log = FeedLog("m42")
    await replay(demo_store().record("m42"), log, template_only, sleep=no_wait)
    entries = [entry.to_wire() for entry in log.entries]
    OUT.write_text(json.dumps(entries, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} entries to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
