"""The Proving Ground in the API: the runs recorded in `eval/results` and the Release Gate's
verdict on them, computed by the same gate CI runs (ADR-014). Public and read-only: scorecards
hold counts, model-written claim text from a synthetic benchmark, and nothing else.
"""

import json
import logging
from functools import cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError

from fourth_official_contracts import Scorecard, parse_scorecard
from fourth_official_proving.gate import gate

logger = logging.getLogger(__name__)

# The recorded runs: production and the v1.4 candidate on the smoke subset, and the template over
# the full benchmark.
RESULTS = {
    "baseline": "production-20.json",
    "candidate": "candidate-20.json",
    "benchmark": "template.json",
}
# A scorecard with every failure listed is well under this.
MAX_BYTES = 1024 * 1024
# The results change only with a release: let browsers and the proxy keep them a while.
CACHE = "public, max-age=300"
UNAVAILABLE = "The Proving Ground's results are not available."


class UnavailableResultsError(Exception):
    """The recorded results are missing or do not read as scorecards."""


def _read(path: Path) -> Scorecard:
    try:
        if path.stat().st_size > MAX_BYTES:
            raise UnavailableResultsError(f"{path.name} is too large")
        return parse_scorecard(json.loads(path.read_bytes()))
    except (OSError, ValueError, RecursionError, ValidationError) as error:
        raise UnavailableResultsError(f"{path.name} does not read") from error


def _results(directory: Path) -> dict[str, Any]:
    cards = {key: _read(directory / name) for key, name in RESULTS.items()}
    verdict = gate(cards["candidate"], cards["baseline"])
    return {**{key: card.to_wire() for key, card in cards.items()}, "verdict": verdict.to_wire()}


def proving_router(directory: Path) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["proving-ground"])
    load = cache(_results)

    @router.get("/proving-ground")
    def proving_ground(response: Response) -> dict[str, Any]:
        try:
            body = load(directory)
        except UnavailableResultsError:
            # Not cached: a later deploy that adds the results is served without a restart.
            logger.warning(
                "the Proving Ground's results are not available under %s", directory.resolve()
            )
            raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
        response.headers["Cache-Control"] = CACHE
        return body

    return router
