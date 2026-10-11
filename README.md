# Fourth Official

**Saguaro Cloud** · Inside the Game: Developer Hackathon (Microsoft × Premier League), October 2026

The control room that lets a league's studio put AI match intelligence on air safely, for every broadcast partner, in every market and every language.

> All data is synthetic. The league, clubs, players and broadcast partners are fictional.

## Status

Phase 0 (foundations). See [`docs/PLAN.md`](docs/PLAN.md) for progress and [`docs/DECISIONS.md`](docs/DECISIONS.md) for architectural decisions.

## Develop

Prerequisites: [uv](https://docs.astral.sh/uv/), Node.js 24 (`.nvmrc`), GNU Make.

```bash
make install   # Python workspace (uv) + web dependencies
make check     # everything CI runs: lint, format, types, tests with coverage
make fmt       # auto-format and fix lint where safe
```

| Path | What |
|---|---|
| `apps/api` | FastAPI gateway (Python 3.12) |
| `apps/web` | Next.js web app (TypeScript) |
| `packages/contracts` | Match event and correction contracts (Pydantic, exported to JSON Schema) |
| `infra/` | Bicep for Azure, with policy tests (`infra/tests`) |
| `scripts/` | Container and deployment smoke tests |
| `docs/` | Plan and architecture decisions |

All changes go through pull requests; `main` is protected and must stay green. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Deploy to Azure

Prerequisites: [Azure Developer CLI](https://aka.ms/azd), Docker, an Azure subscription.

```bash
azd up    # provisions everything in infra/ and deploys both apps
```

The apps scale to zero when idle. In this repository, infrastructure is provisioned by a person and every merge to `main` deploys the apps through GitHub Actions with workload identity federation (no stored credentials). See [ADR-004](docs/DECISIONS.md).

## Licence

[MIT](LICENSE)
