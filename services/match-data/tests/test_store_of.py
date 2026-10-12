"""Any played matches can be served, not only the demo matchday: the benchmark is too."""

from fourth_official_match_data import demo_store, store_of
from fourth_official_simulator.benchmark import benchmark_matches
from fourth_official_simulator.demo import demo_matchday


def test_a_store_serves_the_matches_it_was_given_fully_played() -> None:
    setups = benchmark_matches(2)
    store = store_of(setups)

    assert store.match_ids() == ("m1001", "m1002")
    record = store.record("m1001")
    assert record.live_seq == record.match.events[-1].seq
    assert set(record.club_names) == {setups[0].home.squad.club, setups[0].away.squad.club}


def test_the_demo_store_is_the_demo_matchday() -> None:
    assert demo_store().match_ids() == store_of(demo_matchday()).match_ids()
