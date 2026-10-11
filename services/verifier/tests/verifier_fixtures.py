"""A small match with known facts, and a valid insight about its first goal."""

from typing import Any

from events import pass_, pressure, shot
from fourth_official_contracts import (
    CLUB_NAMES,
    Insight,
    MatchEvent,
    MetricSnapshot,
    Moment,
    parse_insight,
)
from fourth_official_moments.detector import detect
from fourth_official_simulator.squads import generate_squad
from fourth_official_stats.context import MatchContext
from fourth_official_stats.prepare import prepare
from fourth_official_stats.snapshots import SnapshotKey, snapshot
from fourth_official_verifier import MatchFacts
from moment_builders import goal

CTX = MatchContext(match_id="m42", home="HCY", away="NGT")
EVENTS: tuple[MatchEvent, ...] = (
    pass_(1, 10, "HCY"),
    pressure(2, 11, "NGT", "HCY"),
    shot(3, 12, "HCY", outcome="goal"),
    goal(4, 12, "HCY", shot_seq=3, home=1, away=0),
    pass_(5, 14, "NGT"),
    shot(6, 20, "NGT", outcome="goal"),
    goal(7, 20, "NGT", shot_seq=6, home=1, away=1),
)
MATCH = prepare(CTX, EVENTS)
GOAL_MOMENT: Moment = detect(MATCH)[1][0]
POSSESSION: MetricSnapshot = snapshot(
    MATCH, as_of_seq=4, key=SnapshotKey("possession", "HCY", "match")
)
LATER_POSSESSION: MetricSnapshot = snapshot(
    MATCH, as_of_seq=7, key=SnapshotKey("possession", "HCY", "match")
)
# The goal builder credits shirt 9, which the generated squad does not have: give it a player.
PLAYERS = {
    **{p.player_id: p.name for club in ("HCY", "NGT") for p in generate_squad(club, 2026).players},
    "HCY-09": "Ines Okafor",
}
FACTS = MatchFacts(
    match=MATCH,
    club_names={code: CLUB_NAMES[code] for code in ("HCY", "NGT")},
    player_names=PLAYERS,
    snapshots={s.snapshot_id: s for s in (POSSESSION, LATER_POSSESSION)},
)


def insight_wire(
    *claims: dict[str, Any], headline: str = "{{club:HCY}} take the lead"
) -> dict[str, Any]:
    return {
        "insightId": f"in-{GOAL_MOMENT.moment_id.removeprefix('mo-')}-a1",
        "matchId": "m42",
        "momentId": GOAL_MOMENT.moment_id,
        "asOfSeq": GOAL_MOMENT.as_of_seq,
        "locale": "en",
        "headline": headline,
        "claims": list(claims)
        or [
            {
                "claimId": "cl-1",
                "type": "stat",
                "text": (
                    "{{player:HCY-09}} puts {{club:HCY}} ahead in the {{minute:12}}: {{score}}."
                ),
                "evidence": {"eventIds": ["m42-e0003", "m42-e0004"], "metricSnapshotIds": []},
            },
            {
                "claimId": "cl-2",
                "type": "stat",
                "text": "{{club:HCY}} have had {{value:"
                + POSSESSION.snapshot_id
                + "}} of the ball.",
                "evidence": {"eventIds": [], "metricSnapshotIds": [POSSESSION.snapshot_id]},
            },
        ],
        "provenance": {
            "agent": "analyst",
            "promptVersion": "v1.3",
            "model": "fast",
            "producedBy": "model",
        },
    }


def claim(
    text: str, *, events: tuple[str, ...] = ("m42-e0004",), snapshots: tuple[str, ...] = ()
) -> dict[str, Any]:
    return {
        "claimId": "cl-1",
        "type": "stat",
        "text": text,
        "evidence": {"eventIds": list(events), "metricSnapshotIds": list(snapshots)},
    }


def insight(*claims: dict[str, Any], headline: str = "{{club:HCY}} take the lead") -> Insight:
    return parse_insight(insight_wire(*claims, headline=headline))


LOCALES = {"tribuna-austral": "es-MX", "rheinblick-sport": "de-DE", "northlight-sport": "en-GB"}


def localized_wire(
    canonical: dict[str, Any], tenant: str, headline: str, *texts: str
) -> dict[str, Any]:
    """The canonical insight in a partner's words: same claims and evidence, new text."""
    claims = [
        {**claim, "text": text} for claim, text in zip(canonical["claims"], texts, strict=True)
    ]
    return {
        "itemId": f"it-{tenant}-{canonical['insightId']}-v1",
        "tenantId": tenant,
        "locale": LOCALES[tenant],
        "insightId": canonical["insightId"],
        "matchId": canonical["matchId"],
        "momentId": canonical["momentId"],
        "asOfSeq": canonical["asOfSeq"],
        "version": 1,
        "headline": headline,
        "claims": claims,
        "provenance": {
            "agent": "localizer",
            "promptVersion": "v1.0",
            "model": "fast",
            "producedBy": "model",
        },
        "policyVersion": 1,
    }
