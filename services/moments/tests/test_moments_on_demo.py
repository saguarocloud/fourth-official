"""The detector finds the demo matchday's planted storylines (ground truth from the simulator)."""

from functools import cache

import pytest

from fourth_official_contracts import GroundTruth, Moment
from fourth_official_moments.detector import detect
from fourth_official_simulator.demo import demo_matchday
from fourth_official_simulator.engine import play
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import prepare

# Shift moments need a sustained change in five-minute windows: found within ten minutes.
SHIFT_DETECTION_MINUTES = 10
# Truth kinds the detector reports as moments. Reassignments arrive as corrections, and tactical
# shifts other than pressing have no rule yet (docs/moments.md).
DETECTED_KINDS = frozenset({"goal", "red_card", "var_overturn", "pressing_collapse"})


@cache
def demo() -> dict[str, tuple[GroundTruth, tuple[Moment, ...]]]:
    found = {}
    for setup in demo_matchday():
        match = play(setup)
        context = MatchContext(setup.match_id, setup.home.squad.club, setup.away.squad.club)
        found[setup.match_id] = (match.ground_truth, detect(prepare(context, match.events))[1])
    return found


@pytest.mark.parametrize("match_id", ["m42", "m43", "m44"])
def test_every_planted_storyline_is_found(match_id: str) -> None:
    truth, moments = demo()[match_id]
    for story in truth.storylines:
        if story.kind not in DETECTED_KINDS:
            continue
        candidates = [m for m in moments if (m.kind, m.club) == (story.kind, story.club)]
        if story.event_ids:
            assert any(set(m.event_ids) & set(story.event_ids) for m in candidates), story
        else:
            assert any(
                story.minute <= m.clock.minute <= story.minute + SHIFT_DETECTION_MINUTES
                for m in candidates
            ), story


def test_the_featured_press_collapse_is_found_soon_after_it_starts() -> None:
    _, moments = demo()["m42"]
    (collapse,) = [m for m in moments if m.kind == "pressing_collapse"]

    assert collapse.club == "NGT"
    assert 61 < collapse.clock.minute <= 61 + SHIFT_DETECTION_MINUTES
    assert collapse.shifts[0].after < collapse.shifts[0].before


def test_no_pressing_story_is_invented_on_the_demo_matchday() -> None:
    planted = {
        (match_id, s.club)
        for match_id, (truth, _) in demo().items()
        for s in truth.storylines
        if s.kind.startswith("pressing")
    }
    found = {
        (match_id, m.club)
        for match_id, (_, moments) in demo().items()
        for m in moments
        if m.kind.startswith("pressing")
    }

    assert found == planted
