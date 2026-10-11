# syntax=docker/dockerfile:1.7
# Build context: repository root (the uv workspace lockfile lives there).

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so source edits don't invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package fourth-official-api --no-install-workspace
COPY apps/api apps/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package fourth-official-api --no-editable

FROM python:3.12-slim AS runtime
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ARG APP_VERSION=dev
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}
USER 10001
EXPOSE 8000
CMD ["uvicorn", "--factory", "fourth_official_api.main:app_from_env", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
