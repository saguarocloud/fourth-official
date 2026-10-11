# syntax=docker/dockerfile:1.7
# Build context: repository root (the uv workspace lockfile lives there).

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so source edits don't invalidate the dependency layer.
# Every workspace member's manifest is needed for uv to validate the lockfile.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/contracts/pyproject.toml packages/contracts/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package fourth-official-api --no-install-workspace
COPY apps/api apps/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package fourth-official-api --no-editable

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS runtime
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
# Root-owned and read-only to the runtime user: the app cannot modify its own code.
COPY --from=build /app/.venv /app/.venv
ARG APP_VERSION=dev
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}
USER 10001
EXPOSE 8000
# Forwarded headers are not trusted yet: nothing uses the client IP or builds absolute URLs. When
# something does, trust only the Container Apps ingress rather than "*".
CMD ["uvicorn", "--factory", "fourth_official_api.main:app_from_env", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
