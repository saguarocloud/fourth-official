"""The single entry point: events are validated against the match, deduplicated, ordered, bounded,
and placed on a monotone match timeline."""

import pytest

from events import KICKOFF, MATCH, pass_, period_end
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import MAX_EVENTS, prepare

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")


def test_events_come_back_in_match_order() -> None:
    match = prepare(CTX, (pass_(3, 12, "HCY"), pass_(1, 10, "HCY"), pass_(2, 11, "NGT")))

    assert [e.seq for e in match.events] == [1, 2, 3]
    assert match.by_seq[2].seq == 2


def test_only_the_latest_version_of_a_corrected_event_counts() -> None:
    original = pass_(1, 10, "HCY")
    corrected = original.model_copy(
        update={"version": 2, "outcome": "incomplete", "receiver_id": None}
    )

    match = prepare(CTX, (original, corrected))

    assert match.events == (corrected,)


def test_two_different_events_cannot_share_a_sequence_number() -> None:
    clash = pass_(1, 10, "NGT").model_copy(update={"event_id": f"{MATCH}-e0099"})

    with pytest.raises(ValueError, match="seq"):
        prepare(CTX, (pass_(1, 10, "HCY"), clash))


def test_events_from_another_match_are_refused() -> None:
    other = pass_(1, 10, "HCY").model_copy(update={"match_id": "m7", "event_id": "m7-e0001"})

    with pytest.raises(ValueError, match="match"):
        prepare(CTX, (other,))


def test_events_by_a_club_not_in_the_match_are_refused() -> None:
    with pytest.raises(ValueError, match="SLT"):
        prepare(CTX, (pass_(1, 10, "SLT"),))


def test_oversized_matches_are_refused() -> None:
    events = tuple(pass_(i, 10, "HCY") for i in range(1, MAX_EVENTS + 2))

    with pytest.raises(ValueError, match="events"):
        prepare(CTX, events)


def test_match_time_runs_on_through_first_half_added_time() -> None:
    # First half ends at 47:30; the second half restarts its clock at 45:00.
    added_time = pass_(1, 47, "HCY", period=1)
    end = period_end(2, 47, second=30)
    restart = pass_(3, 45, "NGT", second=10)

    match = prepare(CTX, (added_time, end, restart))

    assert match.seconds(added_time) == 47 * 60
    assert match.seconds(restart) == 47 * 60 + 30 + 10
    assert match.seconds(restart) > match.seconds(added_time)


@pytest.mark.parametrize(
    ("match_id", "home", "away"),
    [("m42", "HCY", "HCY"), ("match42", "HCY", "NGT"), ("m42", "hcy", "NGT")],
)
def test_a_malformed_context_is_refused(match_id: str, home: str, away: str) -> None:
    with pytest.raises(ValueError, match="context"):
        MatchContext(match_id=match_id, home=home, away=away)


def test_kickoff_constant_is_utc() -> None:
    assert KICKOFF.tzinfo is not None
