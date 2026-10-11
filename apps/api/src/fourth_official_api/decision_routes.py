"""Editors' decisions on held items: approve to put an item on air, reject (with a reason) to keep
it off. A decision is published on the match's feed as the item's next entry, so every screen and
partner stream sees it at once.

Like starting the matchday, a decision comes only from the studio's own pages: callers must name
themselves in a header a cross-site form cannot send, and a browser request from another origin is
refused. The demo has no sign-in, so the decision is recorded against the partner's duty editor
(docs/DECISIONS.md, ADR-011).
"""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Path, Request, Response
from pydantic import AfterValidator, Field, StringConstraints, model_validator

from fourth_official_api.matchday_routes import (
    START_HEADER,
    START_HEADER_VALUE,
    MatchIdParam,
    TenantIdParam,
    _matchday,
    _tenant,
)
from fourth_official_contracts import WireModel
from fourth_official_contracts.insights import single_line
from fourth_official_replay import DecisionError, UnknownItemError
from fourth_official_replay.errors import FullTimeError, NoRoomOnAirError

ItemIdParam = Annotated[str, Path(max_length=160, pattern=r"^it-[a-z]+(-[a-z]+)*-[A-Za-z0-9_-]+$")]
NO_STORE = {"Cache-Control": "no-store"}


def _line(text: str) -> str:
    single_line(text)
    return text


class DecisionRequest(WireModel):
    decision: Literal["approved", "rejected"]
    # The run the editor saw (the feed's generation): a page left open across a replay cannot
    # decide on the new run's item of the same id.
    generation: Annotated[int, Field(ge=0)]
    # Checked here as the contract checks it, so a bad reason is refused before any work.
    reason: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
            AfterValidator(_line),
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def _a_rejection_says_why(self) -> "DecisionRequest":
        if self.decision == "rejected" and self.reason is None:
            raise ValueError("a rejection gives its reason")
        return self


def _status_of(refused: DecisionError) -> int:
    """409 for a conflict with the item's state; 410 once the match is over; 503 (retry) when
    the partner's graphics are full this minute."""
    if isinstance(refused, FullTimeError):
        return 410
    if isinstance(refused, NoRoomOnAirError):
        return 503
    return 409


def _headers_of(refused: DecisionError) -> dict[str, str]:
    if isinstance(refused, NoRoomOnAirError):
        return {**NO_STORE, "Retry-After": "5"}
    return NO_STORE


def _to_the_millisecond(moment: datetime) -> datetime:
    """The wire writes times to the millisecond: the record keeps exactly what clients see."""
    return moment.replace(microsecond=moment.microsecond // 1000 * 1000)


def decision_router(*, allowed_origins: frozenset[str] = frozenset()) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["approvals"])

    @router.post("/tenants/{tenant_id}/matches/{match_id}/items/{item_id}/decision")
    async def decide(  # noqa: PLR0913 - the item's address, the decision, and the guard headers
        *,
        tenant_id: TenantIdParam,
        match_id: MatchIdParam,
        item_id: ItemIdParam,
        body: DecisionRequest,
        request: Request,
        response: Response,
        requested_by: Annotated[str | None, Header(alias=START_HEADER)] = None,
        origin: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        response.headers.update(NO_STORE)
        if requested_by != START_HEADER_VALUE or (origin and origin not in allowed_origins):
            raise HTTPException(
                status_code=403, detail="decisions are made from the studio", headers=NO_STORE
            )
        policy = _tenant(request, tenant_id)
        try:
            entry = await _matchday(request).decide(
                match_id,
                policy.tenant_id,
                item_id,
                body.decision,
                # Only a rejection keeps a reason.
                reason=body.reason if body.decision == "rejected" else None,
                now=_to_the_millisecond(datetime.now(UTC)),
                generation=body.generation,
            )
        except UnknownItemError as unknown:
            raise HTTPException(status_code=404, detail=str(unknown), headers=NO_STORE) from None
        except DecisionError as refused:
            raise HTTPException(
                status_code=_status_of(refused), detail=str(refused), headers=_headers_of(refused)
            ) from None
        return entry.to_wire()

    return router
