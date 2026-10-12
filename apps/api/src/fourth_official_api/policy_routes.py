"""Policy Studio's API: every partner's policy and its history, edits, and a reset to the
release's policies.

Edits come only from the studio's own pages, as starting the matchday and editors' decisions do:
a header a cross-site form cannot send, and no browser request from another origin. The demo has
no sign-in, so an edit is recorded against the partner's duty editor, a named demo identity, and
the whole studio may make only a few edits a minute. Every edit is kept with who, when and why.
"""

import time
from collections import deque
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from fourth_official_api.matchday_routes import START_HEADER, START_HEADER_VALUE
from fourth_official_contracts.insights import single_line
from fourth_official_policy.book import PolicyBook, StaleVersionError
from fourth_official_policy.store import MAX_POLICY_BYTES, PolicyError

# Edits the whole studio may make in a minute: a demo has many visitors and one set of policies.
EDITS_PER_MINUTE = 10
NO_STORE = {"Cache-Control": "no-store"}


def _one_line(text: str) -> str:
    single_line(text)
    return text


Reason = Annotated[str, StringConstraints(min_length=1, max_length=200), AfterValidator(_one_line)]


class EditRequest(BaseModel):
    """A partner's next policy, from the form (`policy`) or the raw view (`yaml`)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=False, hide_input_in_errors=True)

    policy: dict[str, Any] | None = None
    yaml: Annotated[str, StringConstraints(max_length=MAX_POLICY_BYTES)] | None = None
    base_version: Annotated[int, Field(alias="baseVersion", ge=1)]
    reason: Reason

    @model_validator(mode="after")
    def _one_source(self) -> "EditRequest":
        if (self.policy is None) == (self.yaml is None):
            raise ValueError("send the policy either as fields or as YAML, not both")
        return self


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    reason: Reason


class _Window:
    """At most `limit` events in any minute."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._times: deque[float] = deque()

    def take(self) -> int:
        """0 if allowed, else the seconds until it would be."""
        now = time.monotonic()
        while self._times and now - self._times[0] >= 60:
            self._times.popleft()
        if len(self._times) >= self._limit:
            return max(1, int(60 - (now - self._times[0])))
        self._times.append(now)
        return 0


def _book(request: Request) -> PolicyBook:
    book: PolicyBook = request.app.state.policies
    return book


def policy_router(*, allowed_origins: frozenset[str] = frozenset()) -> APIRouter:
    router = APIRouter(prefix="/api/policies", tags=["policies"])
    edits = _Window(EDITS_PER_MINUTE)

    def guard(requested_by: str | None, origin: str | None) -> None:
        if requested_by != START_HEADER_VALUE or (origin and origin not in allowed_origins):
            raise HTTPException(status_code=403, detail="Policies are edited from the studio only.")
        wait = edits.take()
        if wait:
            raise HTTPException(
                status_code=429,
                detail="Too many edits just now. Wait a moment and try again.",
                headers={"Retry-After": str(wait)},
            )

    @router.get("")
    def policies(request: Request, response: Response) -> dict[str, list[dict[str, Any]]]:
        """Every partner's current policy."""
        response.headers.update(NO_STORE)
        book = _book(request)
        return {"policies": [book.current(t).to_wire() for t in sorted(book.tenants())]}

    @router.get("/{tenant_id}")
    def history(tenant_id: str, request: Request, response: Response) -> dict[str, Any]:
        """Every version of the partner's policy, oldest first, with the change that made it."""
        book = _book(request)
        if tenant_id not in book.tenants():
            raise HTTPException(status_code=404, detail="unknown partner")
        response.headers.update(NO_STORE)
        return book.history(tenant_id).to_wire()

    @router.post("/reset")
    async def reset(
        body: ResetRequest,
        request: Request,
        response: Response,
        *,
        requested_by: Annotated[str | None, Header(alias=START_HEADER)] = None,
        origin: Annotated[str | None, Header()] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Every partner's policy back to the release's, as its next version."""
        guard(requested_by, origin)
        changes = await _book(request).reset(reason=body.reason)
        response.headers.update(NO_STORE)
        return {"changes": [c.to_wire() for c in changes]}

    @router.post("/{tenant_id}")
    async def edit(
        tenant_id: str,
        body: EditRequest,
        request: Request,
        response: Response,
        *,
        requested_by: Annotated[str | None, Header(alias=START_HEADER)] = None,
        origin: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """The partner's next version. 422 with the reason in words if it is not a valid policy
        (or changes nothing), 409 if it was made on a version that is no longer current."""
        book = _book(request)
        if tenant_id not in book.tenants():
            raise HTTPException(status_code=404, detail="unknown partner")
        guard(requested_by, origin)
        proposed: dict[str, Any] | str = body.policy if body.policy is not None else body.yaml or ""
        try:
            change = await book.edit(
                tenant_id, proposed, base_version=body.base_version, reason=body.reason
            )
        except StaleVersionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        except PolicyError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        response.headers.update(NO_STORE)
        return change.to_wire()

    return router
