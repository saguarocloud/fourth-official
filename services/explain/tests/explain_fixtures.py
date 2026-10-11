"""The featured demo match, its moments, and facts the Verifier can check them against."""

from functools import cache

from fourth_official_contracts import CLUB_NAMES, Moment
from fourth_official_explain.snapshots import ComputedSnapshots
from fourth_official_match_data import demo_store
from fourth_official_moments.detector import detect
from fourth_official_simulator.demo import demo_matchday
from fourth_official_simulator.engine import play
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import prepare
from fourth_official_verifier import MatchFacts


@cache
def featured() -> tuple[MatchFacts, tuple[Moment, ...]]:
    setup = demo_matchday()[0]
    home, away = setup.home.squad, setup.away.squad
    match = prepare(MatchContext(setup.match_id, home.club, away.club), play(setup).events)
    facts = MatchFacts(
        match=match,
        club_names={c: CLUB_NAMES[c] for c in (home.club, away.club)},
        player_names={p.player_id: p.name for s in (home, away) for p in s.players},
        snapshots=ComputedSnapshots(match),
        # Voids in force from their VAR decisions, as the match data store reports them.
        voided=demo_store().record(setup.match_id).void_seqs(),
    )
    return facts, detect(match)[1]


def moment(kind: str) -> Moment:
    return next(m for m in featured()[1] if m.kind == kind)
