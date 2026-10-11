# Local entry points. CI runs the same commands (.github/workflows/ci.yml).
.PHONY: install check check-python check-web test fmt

install:
	uv sync --all-packages
	cd apps/web && npm ci

check: check-python check-web

check-python:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest --cov

check-web:
	cd apps/web && npm run lint && npm run format:check && npm run typecheck && npm run coverage

test:
	uv run pytest
	cd apps/web && npm test

fmt:
	uv run ruff format .
	uv run ruff check --fix .
	cd apps/web && npm run format
