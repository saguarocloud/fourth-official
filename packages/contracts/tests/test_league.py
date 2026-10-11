"""The league's clubs are the same everywhere: contracts, simulator and web."""

import re
from pathlib import Path

from fourth_official_contracts import CLUB_NAMES
from fourth_official_simulator.squads import CLUB_CODES

WEB_CLUBS = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "domain" / "matchday.ts"


def test_the_simulator_plays_exactly_the_league_clubs() -> None:
    assert set(CLUB_NAMES) == set(CLUB_CODES)


def test_the_web_app_names_clubs_the_same_way() -> None:
    web = dict(re.findall(r'code: "([A-Z]{3})", name: "([^"]+)"', WEB_CLUBS.read_text()))

    assert web == dict(CLUB_NAMES)
