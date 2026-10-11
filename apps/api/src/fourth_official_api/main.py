"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict

from fourth_official_api.explainers import foundry_explainer, template_explainer
from fourth_official_api.matchday_routes import matchday_router
from fourth_official_api.security import SecurityHeaders
from fourth_official_api.settings import Settings
from fourth_official_api.start_ledger import blob_start_ledger
from fourth_official_match_data import MatchStore, demo_store
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


def create_app(
    settings: Settings, *, matchday: Matchday | None = None, ledger: StartLedger | None = None
) -> FastAPI:
    """Build the API with explicit settings, so tests never depend on process environment. A
    given `matchday` is used as is; otherwise one is built at startup with the Analyst on Foundry
    when configured, or the templates alone."""
    store = demo_store()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
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
                explainer = (
                    await stack.enter_async_context(foundry_explainer(settings.foundry))
                    if settings.foundry
                    else template_explainer
                )
                day = Matchday(
                    store,
                    explainer,
                    config=ReplayConfig(speed=settings.replay_speed),
                    ledger=starts,
                    runs_per_day=settings.runs_per_day,
                )
            app.state.matchday = day
            try:
                yield
            finally:
                await day.stop()

    app = FastAPI(title="Fourth Official API", version=settings.version, lifespan=lifespan)

    @app.get("/healthz", response_model=Health, tags=["ops"])
    def healthz(response: Response) -> Health:
        # Probes and smoke tests must always see live state, never a cached copy.
        response.headers["Cache-Control"] = "no-store"
        return Health(status="ok", service=SERVICE_NAME, version=settings.version)

    app.include_router(matchday_router(_summaries(store)))
    docs = [path for path in (app.docs_url, app.redoc_url) if path is not None]
    app.add_middleware(SecurityHeaders, docs_paths=docs)
    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn: `uvicorn --factory fourth_official_api.main:app_from_env`."""
    return create_app(Settings.from_env())
