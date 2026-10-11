# Local entry points. CI runs the same commands (.github/workflows/ci.yml).
.PHONY: install check check-python check-web check-infra smoke-containers contracts test fmt

install:
	uv sync --all-packages
	cd apps/web && npm ci

check: check-python check-web check-infra

check-python:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest --cov

check-web:
	cd apps/web && npm run lint && npm run format:check && npm run typecheck && npm run coverage

check-infra:
	scripts/lint-bicep.sh
	uv run pytest infra/tests --no-cov

smoke-containers:
	docker build -f apps/api/Dockerfile --build-arg APP_VERSION=local -t fo-api:local .
	docker build -f apps/web/Dockerfile --build-arg APP_VERSION=local -t fo-web:local apps/web
	scripts/smoke-container.sh fo-api:local 8000 fourth-official-api local
	scripts/smoke-container.sh fo-web:local 3000 fourth-official-web local

contracts:
	uv run python -m fourth_official_contracts.schema

test:
	uv run pytest
	cd apps/web && npm test

fmt:
	uv run ruff format .
	uv run ruff check --fix .
	cd apps/web && npm run format
