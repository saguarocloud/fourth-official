"""FastAPI application factory."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict

from fourth_official_api import telemetry
from fourth_official_api.decision_routes import decision_router
from fourth_official_api.explainers import (
    foundry_explainer,
    foundry_localizer_for,
    partners_for,
    template_explainer,
)
from fourth_official_api.matchday_routes import matchday_router
from fourth_official_api.operations_routes import operations_router
from fourth_official_api.policy_routes import policy_router
from fourth_official_api.policy_store import azure_policy_book
from fourth_official_api.provenance import Issuer, provenance_router
from fourth_official_api.proving import proving_router
from fourth_official_api.security import SecurityHeaders
from fourth_official_api.settings import Settings
from fourth_official_api.start_ledger import blob_start_ledger
from fourth_official_api.wall_routes import wall_router
from fourth_official_contracts import TenantPolicy
from fourth_official_match_data import MatchStore, demo_store
from fourth_official_policy import bundled_store
from fourth_official_policy.book import BookStore, InMemoryBookStore, PolicyBook
from fourth_official_provenance import InMemoryStore, LocalSigner
from fourth_official_provenance.azure import azure_provenance
from fourth_official_replay import Matchday, ReplayConfig, StartLedger

SERVICE_NAME = "fourth-official-api"


class Health(BaseModel):
    """Liveness payload returned by `GET /healthz`."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: str
    version: str


def _summaries(store: MatchStore) -> dict[str, dict[str, str]]:
    summaries = {}
    for match_id in store.match_ids():
        record = store.record(match_id)
        home, away = record.match.context.home, record.match.context.away
        summaries[match_id] = {
            "home": home,
            "away": away,
            "home_name": record.club_names[home],
            "away_name": record.club_names[away],
        }
    return summaries


async def _open_book(
    stack: AsyncExitStack,
    settings: Settings,
    policies: Sequence[TenantPolicy],
    store: BookStore | None,
) -> PolicyBook:
    """Policy Studio's book: kept in Blob Storage when configured, else in memory."""
    if store is None and settings.policy_book is not None:
        store = await stack.enter_async_context(
            azure_policy_book(settings.policy_book.container_url, settings.policy_book.client_id)
        )
    book = PolicyBook(policies, store if store is not None else InMemoryBookStore())
    await book.open()
    return book


def create_app(
    settings: Settings,
    *,
    matchday: Matchday | None = None,
    ledger: StartLedger | None = None,
    provenance: Issuer | None = None,
    policy_store: BookStore | None = None,
) -> FastAPI:
    """Build the API with explicit settings, so tests never depend on process environment. A
    given `matchday` is used as is; otherwise one is built at startup with the Analyst on Foundry
    when configured, or the templates alone."""
    store = demo_store()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            policies = [loaded.policy for loaded in bundled_store().all()]
            book = await _open_book(stack, settings, policies, policy_store)
            app.state.policies = book
            day = matchday
            starts = ledger
            if starts is None and settings.start_ledger is not None:
                starts = await stack.enter_async_context(
                    blob_start_ledger(settings.start_ledger.url, settings.start_ledger.client_id)
                )
            if day is None:
                if settings.foundry and starts is None:
                    # Model spend is bounded by the matchday's guards, which must survive restarts.
                    raise RuntimeError(
                        "the Analyst needs a durable start ledger; none is configured"
                    )
                if settings.foundry and provenance is None and settings.provenance is None:
                    # Model-written items are signed with the studio's vault key, never a key
                    # that lives as long as the process (ADR-013).
                    raise RuntimeError(
                        "model-written items need the studio's signing key; none is set"
                    )
                explainer = (
                    await stack.enter_async_context(foundry_explainer(settings.foundry))
                    if settings.foundry
                    else template_explainer
                )
                localizer = (
                    await stack.enter_async_context(foundry_localizer_for(settings.foundry))
                    if settings.foundry
                    else None
                )
                day = Matchday(
                    store,
                    explainer,
                    config=ReplayConfig(speed=settings.replay_speed),
                    ledger=starts,
                    runs_per_day=settings.runs_per_day,
                    partners=partners_for(policies, localizer, book),
                )
            app.state.matchday = day
            issuer = provenance
            if issuer is None:
                if settings.provenance is not None:
                    signer, records = await stack.enter_async_context(
                        azure_provenance(
                            settings.provenance.key_id,
                            settings.provenance.container_url,
                            settings.provenance.client_id,
                        )
                    )
                    issuer = Issuer(signer, records)
                else:
                    # Development: a key that lives as long as the process, records in memory.
                    issuer = Issuer(LocalSigner(), InMemoryStore())
            app.state.provenance = issuer
            followers = [
                asyncio.create_task(
                    issuer.follow(day.feed(match_id)), name=f"provenance-{match_id}"
                )
                for match_id in store.match_ids()
            ]
            try:
                yield
            finally:
                for follower in followers:
                    follower.cancel()
                await asyncio.gather(*followers, return_exceptions=True)
                await day.stop()

    app = FastAPI(title="Fourth Official API", version=settings.version, lifespan=lifespan)

    @app.get("/healthz", response_model=Health, tags=["ops"])
    def healthz(response: Response) -> Health:
        # Probes and smoke tests must always see live state, never a cached copy.
        response.headers["Cache-Control"] = "no-store"
        return Health(status="ok", service=SERVICE_NAME, version=settings.version)

    app.include_router(matchday_router(_summaries(store)))
    app.include_router(decision_router())
    app.include_router(operations_router())
    app.include_router(wall_router())
    app.include_router(policy_router())
    app.include_router(provenance_router())
    app.include_router(proving_router(settings.proving_results))
    docs = [path for path in (app.docs_url, app.redoc_url) if path is not None]
    app.add_middleware(SecurityHeaders, docs_paths=docs)
    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn: `uvicorn --factory fourth_official_api.main:app_from_env`."""
    settings = Settings.from_env()
    # Before the app is built, so every model call is traced; then its requests.
    traced = telemetry.start(settings.telemetry)
    app = create_app(settings)
    if traced:
        telemetry.instrument(app)
    return app
