"""A provenance record: everything about how a partner's item came to be, signed by the studio so
anyone can check it was not changed since."""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import (
    ProvenanceRecord,
    SignedProvenance,
    canonical_bytes,
    parse_signed_provenance,
)

RECORD: dict[str, Any] = {
    "itemId": "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1",
    "tenantId": "tribuna-austral",
    "matchId": "m42",
    "insightId": "in-m42-goal-HCY-s0287-a1",
    "version": 1,
    "locale": "es-MX",
    "state": "on_air",
    "issuer": "Meridian League Studios",
    "issuedAt": "2026-10-11T15:00:00.000Z",
    "feedEntry": 131,
    "headline": "Gol de Harbour City",
    "claims": [
        {
            "text": "Niklas Navarro-Gil marca para Harbour City en el 12': 1\u20130.",
            "evidence": {"eventIds": ["m42-e0286", "m42-e0287"], "metricSnapshotIds": []},
        }
    ],
    "canonical": {
        "agent": "analyst",
        "promptVersion": "v1.2",
        "model": "fast",
        "producedBy": "model",
    },
    "localized": {
        "agent": "localizer",
        "promptVersion": "v1.0",
        "model": "fast",
        "producedBy": "model",
    },
    "attempts": [
        {
            "number": 1,
            "agent": "localizer",
            "model": "fast",
            "outcome": "passed",
            "findings": [],
            "error": None,
        }
    ],
    "disclosure": {
        "label": "Asistido por IA · Revisado por T. Ibarra",
        "mode": "label-all",
        "reason": "ai_assisted_reviewed",
    },
    "approval": {
        "editor": "T. Ibarra",
        "decidedAt": "2026-10-11T15:00:00.000Z",
        "decision": "approved",
        "reason": None,
    },
    "supersedes": None,
    "corrections": [],
}

SIGNED: dict[str, Any] = {
    "record": RECORD,
    "contentHash": "a" * 64,
    "signature": "c2lnbmF0dXJl",
    "algorithm": "ES256",
    "keyId": "https://kv-x.vault.azure.net/keys/provenance/0123456789abcdef0123456789abcdef",
}


def changed(base: dict[str, Any], path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    data = copy.deepcopy(base)
    target: Any = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


def test_a_signed_record_round_trips_on_the_wire() -> None:
    signed = parse_signed_provenance(SIGNED)

    assert isinstance(signed, SignedProvenance)
    assert isinstance(signed.record, ProvenanceRecord)
    assert signed.to_wire() == SIGNED


def test_the_canonical_bytes_are_the_same_however_the_record_was_written() -> None:
    record = parse_signed_provenance(SIGNED).record
    reordered = parse_signed_provenance(
        {**SIGNED, "record": dict(reversed(list(RECORD.items())))}
    ).record

    assert canonical_bytes(record) == canonical_bytes(reordered)
    assert canonical_bytes(record).startswith(b'{"approval":')


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (
            ("record", "itemId"),
            "it-northlight-sport-in-m42-goal-HCY-s0287-a1-v1",
        ),  # another partner
        (("record", "version"), 2),  # the item id names version 1
        (("record", "matchId"), "m43"),
        (("record", "locale"), "en-GB"),
        (("record", "claims"), []),
        (("contentHash",), "not-a-hash"),
        (("algorithm",), "none"),
        (("signature",), ""),
        (("record", "headline"), "two\nlines"),
    ],
)
def test_an_inconsistent_record_is_refused(path: tuple[str | int, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        parse_signed_provenance(changed(SIGNED, path, value))
