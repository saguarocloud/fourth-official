"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict

from fourth_official_api.explainers import foundry_explainer, template_explainer
from fourth_official_api.matchday_routes import matchday_router
from fourth_official_api.settings import Settings
from fourth_official_match_data import MatchStore, demo_store
from fourth_official_replay import Matchday

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


def create_app(settings: Settings, *, matchday: Matchday | None = None) -> FastAPI:
    """Build the API with explicit settings, so tests never depend on process environment. A
    given `matchday` is used as is; otherwise one is built at startup with the Analyst on Foundry
    when configured, or the templates alone."""
    store = demo_store()
    days: list[Matchday] = [matchday] if matchday else []

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            if not days:
                explainer = (
                    await stack.enter_async_context(foundry_explainer(settings.foundry))
                    if settings.foundry
                    else template_explainer
                )
                days.append(Matchday(store, explainer))
            try:
                yield
            finally:
                await days[0].stop()

    app = FastAPI(title="Fourth Official API", version=settings.version, lifespan=lifespan)

    @app.get("/healthz", response_model=Health, tags=["ops"])
    def healthz(response: Response) -> Health:
        # Probes and smoke tests must always see live state, never a cached copy.
        response.headers["Cache-Control"] = "no-store"
        return Health(status="ok", service=SERVICE_NAME, version=settings.version)

    app.include_router(matchday_router(lambda: days[0], _summaries(store)))
    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn: `uvicorn --factory fourth_official_api.main:app_from_env`."""
    return create_app(Settings.from_env())
