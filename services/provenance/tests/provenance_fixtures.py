"""The featured match's recorded feed with every partner's items (the web app's fixture)."""

import json
from pathlib import Path

from fourth_official_contracts import FeedEntry, parse_feed_entry

_FIXTURE = Path(__file__).parents[3] / "apps/web/src/fixtures/feed-m42-partners.json"
FEED: list[FeedEntry] = [
    parse_feed_entry(raw) for raw in json.loads(_FIXTURE.read_text(encoding="utf-8"))
]
