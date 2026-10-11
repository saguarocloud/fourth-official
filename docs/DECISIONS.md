# Architecture decisions

One entry per decision: context, options, choice, consequences. Newest last.

---

## ADR-001: Azure region is East US 2

**Date:** 2026-10-10 · **Status:** Accepted

**Context.** We need one region that offers Microsoft Foundry model deployments, Azure AI Content Safety, Azure AI Speech, Container Apps, Event Hubs, Cosmos DB, Web PubSub, Key Vault and API Management. We checked 14 candidate regions on 2026-10-10 with `az cognitiveservices model list`, `az cognitiveservices account list-skus` and provider location queries.

**Options.**
- `eastus2`: every service is available; the widest SKU coverage per model (Global, US Data Zone, Standard); low latency to the team (Mexico City) and US-based judges.
- `swedencentral`: every service is available; supports a story that EU tenants' data stays in the EU. Further from the team, and its quota is identical to East US 2.
- `mexicocentral`: ruled out, because Foundry, Content Safety, Speech and Web PubSub are all unavailable there.

**Choice.** `eastus2`.

**Consequences.**
- Bot Service is deployed as a `global` resource, so the region doesn't affect it.
- Model quota on the new subscription is the real constraint, not the region. Today the subscription has quota for gpt-5-mini (500K tokens/min), gpt-4.1-mini (200K), o4-mini (100K) and several open models (gpt-oss-120b, grok-4-fast, DeepSeek, Llama). It has **zero** quota for gpt-5, gpt-5.4, gpt-5.5 and gpt-5.6. A quota request for a stronger `quality` model is pending. Model deployment names stay in configuration, so swapping models needs no code change.
- EU data residency (Sweden Central plus an EU Data Zone) belongs in the path-to-production story, not the hackathon deployment.

---

## ADR-002: MIT licence; repository public from day one; all changes through pull requests

**Date:** 2026-10-10 · **Status:** Accepted (revised the same day: originally private until submission)

**Context.** The Official Rules require a public repository and grant Microsoft and the Premier League a broad licence to the entry. Judges review the repository itself, so its history and process are part of what they score.

**Choice.**
- Licence: MIT.
- `saguarocloud/fourth-official` is **public now**. Strategy documents that should not be visible to competing entrants stay outside the repository.
- `main` is protected by the `protect-main` ruleset: changes land only through squash-merged pull requests, with linear history, resolved review threads, no force pushes and no branch deletion. The `ci-ok` check is required once CI exists.
- No proprietary Saguaro Cloud IP goes in the repository. Tenant and subscription IDs live in `azd env`, `.env` or GitHub environment secrets, never in tracked files.

**Consequences.** Competitors can see our direction early, so the repository leads with engineering quality rather than the pitch. CI badges, Codespaces links and the commit history work for judges from day one.

---

## ADR-003: Python 3.12 with uv for services; Next.js with TypeScript for the web app

**Date:** 2026-10-10 · **Status:** Accepted

**Context.** We considered Go and Python for the backend. Microsoft Agent Framework, a named hero technology, ships for Python and .NET only. The Foundry SDK, Content Safety, the official MCP SDK and NumPy (for metrics) are all first-class in Python. Our load (3 matches × 23 tracked objects × 5 Hz) does not need Go's performance.

**Choice.**
- **Services:** Python 3.12, managed with **uv** as a single workspace (`uv.lock` committed). FastAPI for HTTP. Frozen Pydantic models and frozen dataclasses for data, in line with our immutability rule.
- **Web:** Next.js (App Router), TypeScript in strict mode (plus `noUncheckedIndexedAccess`), Tailwind CSS, npm with a committed lockfile. The design system is built with the impeccable design workflow.
- **Quality gates (CI and `make check`):**
  - Python: ruff (lint, including bandit security rules, and format), mypy `--strict` over source and tests, pytest with warnings treated as errors, branch coverage of at least 80%.
  - Web: ESLint with zero warnings, Prettier, `tsc`, Vitest with React Testing Library and coverage of at least 80%, and a production build.
- **Process:** test-driven development. Every behaviour starts as a failing test. Domain code (stats, verification, policy, corrections) is pure and sits behind ports. Adapters for Azure services get in-memory fakes and contract tests.
- **Supply chain:** GitHub Actions are pinned to commit SHAs. Dependabot handles uv, npm and Actions updates.

**Consequences.** One backend language means one set of generated contract types and one test toolchain. Go stays an option for a hot path if profiling ever demands it.

---

## ADR-004: Bicep + azd; infrastructure provisioned locally, applications deployed by GitHub Actions

**Date:** 2026-10-10 · **Status:** Accepted (implementation lands with the infrastructure pull request)

**Context.** We want a Microsoft-native toolchain (Pulumi was considered and set aside), a one-command `azd up` for judges, and least privilege for automation.

**Choice.**
- Infrastructure as code: **Bicep**, driven by the **Azure Developer CLI (`azd`)**.
- **`azd provision` runs locally**, by a subscription Owner. Provisioning also creates the GitHub Actions deploy identity: a user-assigned managed identity with a **federated credential** (workload identity federation) for the GitHub `dev` environment. No client secret exists anywhere.
- **GitHub Actions only runs `azd deploy`**: it builds images, pushes them to the registry and updates the Container Apps. Its identity holds **AcrPush** and **Container Apps Contributor** on the app resource group, and nothing that can create resources or grant roles.
- Container registry: **Azure Container Registry, Basic tier**, with the admin user disabled. Container Apps pull with their own managed identity (AcrPull).
- Budget: $100/month on the subscription, with alerts at 25/50/75/100%.

**Consequences.** Infrastructure changes are reviewed in pull requests but applied by a person, which suits a small team and a fixed deadline. Application releases are fully automated on every merge to `main`.
