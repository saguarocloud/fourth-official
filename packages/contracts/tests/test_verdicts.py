"""Verdict contract: the deterministic Verifier's decision on an insight, with its reasons."""

from typing import Any

import pytest
from pydantic import ValidationError

from fourth_official_contracts import Verdict, parse_verdict

PASSED: dict[str, Any] = {
    "insightId": "in-m42-goal-HCY-s0287-a1",
    "matchId": "m42",
    "passed": True,
    "findings": [],
}
FAILED: dict[str, Any] = PASSED | {
    "passed": False,
    "findings": [
        {"claimId": "cl-1", "code": "BARE_NUMBER", "detail": "'3' is not rendered from evidence"},
        {"claimId": None, "code": "UNKNOWN_CLUB", "detail": "SLT is not playing"},
    ],
}


def test_verdicts_round_trip_the_wire() -> None:
    for wire in (PASSED, FAILED):
        assert parse_verdict(wire).to_wire() == wire
    assert isinstance(parse_verdict(PASSED), Verdict)


@pytest.mark.parametrize(
    ("wire", "message"),
    [
        (PASSED | {"findings": FAILED["findings"]}, "passes only without findings"),
        (FAILED | {"findings": []}, "passes only without findings"),
        (PASSED | {"insightId": "in-m7-goal-HCY-s0287-a1"}, "another match"),
        (FAILED | {"findings": [FAILED["findings"][0] | {"code": "MADE_UP"}]}, "code"),
        (FAILED | {"findings": [FAILED["findings"][0] | {"detail": "x" * 201}]}, "detail"),
    ],
)
def test_incoherent_verdicts_are_refused(wire: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_verdict(wire)
