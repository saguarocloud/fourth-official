"""FastAPI application factory."""

from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel, ConfigDict

from fourth_official_api.settings import Settings

SERVICE_NAME = "fourth-official-api"


class Health(BaseModel):
    """Liveness payload returned by `GET /healthz`."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: str
    version: str


def create_app(settings: Settings) -> FastAPI:
    """Build the API with explicit settings, so tests never depend on process environment."""
    app = FastAPI(title="Fourth Official API", version=settings.version)

    @app.get("/healthz", response_model=Health, tags=["ops"])
    def healthz(response: Response) -> Health:
        # Probes and smoke tests must always see live state, never a cached copy.
        response.headers["Cache-Control"] = "no-store"
        return Health(status="ok", service=SERVICE_NAME, version=settings.version)

    return app


def app_from_env() -> FastAPI:
    """Entry point for uvicorn: `uvicorn --factory fourth_official_api.main:app_from_env`."""
    return create_app(Settings.from_env())
