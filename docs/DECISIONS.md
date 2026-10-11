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

**Date:** 2026-10-10 · **Status:** Accepted, implemented 2026-10-11

**Context.** We want a Microsoft-native toolchain (Pulumi was considered and set aside), a one-command `azd up` for judges, and least privilege for automation.

**Choice.**
- Infrastructure as code: **Bicep**, driven by the **Azure Developer CLI (`azd`)**.
- **`azd provision` runs locally**, by a subscription Owner. Provisioning also creates the GitHub Actions deploy identity: a user-assigned managed identity with a **federated credential** (workload identity federation) for the GitHub `dev` environment. No client secret exists anywhere.
- **GitHub Actions only runs `azd deploy`**: it builds images, pushes them to the registry and releases new revisions. Its identity holds **AcrPush** (registry), **Container Apps Contributor** (each app, plus the environment, where it amounts to read and join because its write actions do not apply at that scope; never the resource group), **Managed Identity Operator** (the apps' runtime identity only, because a revision update re-asserts it) and **Reader** (resource group, so azd can find the apps). Nothing it holds can create resources or grant roles.
- Container registry: **Azure Container Registry, Basic tier**, with the admin user disabled. Container Apps pull with their own managed identity (AcrPull).
- Budget: $100/month on the subscription, with alerts at 25/50/75/100%.

**Implementation notes.**
- `infra/main.bicep` (subscription scope) creates the resource group, Log Analytics (30-day retention, 0.5 GB/day ingestion cap), workspace-based Application Insights (local auth disabled), ACR Basic, the Container Apps environment (Consumption profile only), the `api` and `web` apps, both identities, and the budget.
- **Container apps scale to zero** (`minReplicas: 0`, HTTP concurrency rule), so idle time costs nothing. The trade-off is a cold start of a few seconds on the first request; revisit for the judging week if needed.
- Apps pull from ACR with a dedicated user-assigned identity holding only AcrPull. No registry passwords or app secrets exist.
- Until the first `azd deploy`, apps run a public placeholder image. `fetch-container-image.bicep` keeps the deployed image when provisioning re-runs.
- The deploy identity and budget are optional (`GITHUB_DEPLOY_REPOSITORY`, `BUDGET_CONTACT_EMAIL`), so anyone can run `azd up` in their own subscription without them.
- Container logs reach Log Analytics through Azure Monitor diagnostic settings; the workspace has shared-key access disabled, so no workspace key appears anywhere.
- The federated credential's subject comes from GitHub's own report of the repository's OIDC subject prefix (`actions/oidc/customization/sub`). This repository uses **immutable, ID-based subjects** (`repo:owner@<id>/name@<id>:environment:dev`), so a deleted and re-created repository with the same name can never obtain a token. Renaming the repository changes the subject too: re-run `azd provision` after a rename.
- `infra/hooks/preprovision.sh` detects which apps already exist (by their `azd-service-name` tag), so re-provisioning keeps the deployed images; azd does not refresh that flag itself. When `GITHUB_DEPLOY_REPOSITORY` is set it also reads and strictly validates the repository's OIDC subject prefix (it must name exactly that repository), which requires an authenticated `gh`. Both hooks fail closed and have behavioural tests (`infra/tests/test_hooks.py`).
- `infra/hooks/postprovision.sh` writes the GitHub environment's secrets (client, tenant and subscription IDs: identifiers, not credentials) and variables after provisioning, preserves any reviewers configured in GitHub, and leaves `main` as the only branch allowed to deploy.
- Base images and the placeholder image are pinned by digest; Dependabot updates them. CI scans both images with Trivy and fails on fixable critical or high vulnerabilities.
- **Policy tests** (`infra/tests`) compile the Bicep and assert the rules above: scale to zero, no admin user, managed-identity pulls, HTTPS only, health probes, exact role sets for both identities and the narrowest scope for every role, no Owner/Contributor/role-granting roles anywhere, keyless logging, a federated credential scoped to one GitHub environment, budget thresholds, no secret-like outputs, and the wiring between `azure.yaml`, the Bicep outputs, the hooks and the deploy workflow.

**Consequences.** Infrastructure changes are reviewed in pull requests but applied by a person (`azd provision --preview`, then `azd provision`), which suits a small team and a fixed deadline. Application releases are fully automated on every merge to `main`, followed by smoke tests that check the live version matches the commit.

---

## ADR-005: Pydantic models are the source of truth for wire contracts

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** Match events and corrections cross every boundary in the system: simulator → Event Hubs → stats engine → agents → API → web. The plan called for one source of truth with generated types for each language. The choice is which artefact is the source.

**Options.**
- JSON Schema written by hand, with Pydantic and TypeScript generated from it. Generated Python is hard to read and cannot express cross-field rules (a completed pass needs a receiver on the same team).
- **Hand-written Pydantic models, with JSON Schema exported from them, and TypeScript generated from that schema.**

**Choice.** Hand-written, frozen Pydantic models in `packages/contracts` (`fourth_official_contracts`):
- Immutable, camelCase on the wire (parsed by alias only; every dump is camelCase), unknown fields refused, timestamps always UTC with millisecond precision.
- **Strict at the boundary:** a value must already have the JSON Schema's type (`"187"` is not an integer, `"yes"` is not a boolean, an epoch number is not a timestamp). Identifiers use ASCII digits with bounded length; every integer and float has an upper bound; NaN and infinity are refused; validation errors never echo the input.
- Discriminated unions: `MatchEvent` by `type` (19 event types), `Correction` by `kind` (`EVENT_VOIDED`, `EVENT_AMENDED`).
- Domain rules live in the models: an event and every event it references (shot, foul, VAR target) belong to its match, and no event references itself; a VAR decision's reason matches its outcome; own goals need no shot; players play for the team they act for; opponents play for the other side; a completed pass has a different receiver on the same team; goal credit is consistent (own goals, assists); clock minutes fit their period (up to 15 minutes of added time); coordinates fit a 105 × 68 m pitch; a correction always creates a new version and an amendment changes at least one field.
- Corrections share `CorrectionBase`; kinds that target an event add `EventTargeting`. A future kind that targets something else (for example a provider restating a metric) adds its own target fields and a new `kind`. Amendments change only the fields present, never set a fact to null (an assist may be removed), and never mix goal credit with a card.
- `packages/contracts/schemas/*.schema.json` (JSON Schema 2020-12) are generated by `make contracts`, and a test fails if they drift from the models.
- TypeScript types will be generated from those schemas when the web app first consumes events.

**Consequences.** Contract rules are enforced at every boundary that parses with these models, and are readable as ordinary Python. Non-Python consumers get the structural schema (types, ranges, patterns); cross-field rules are only enforced in Python, which is where all producers and validators run.

**Known limits, deliberately out of scope:** no extra time or penalty shoot-outs (the synthetic league has none); the models do not check geometry against event kind (a corner taken from the corner arc, a pass whose origin equals its end) or sequences across events (an interception followed by the matching possession change). Those belong to the simulator's realism tests and the stats engine, which see whole matches.

---

## ADR-006: Claims reference facts with markup; code renders every number and name

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** The product promise is that a language model never calculates a number, and that every published claim can be traced to match data. The Verifier must block wrong numbers, invented players, wrong scorelines and future leakage every time. If the Analyst wrote free text, the Verifier would have to parse numbers and names out of prose, decide which snapshot each number came from, and allow for rounding. That makes it heuristic in exactly the place where it must be certain.

**Options.**
- Free text, with the Verifier extracting and matching numbers and names. This is fragile across phrasing, rounding and languages, and an extractor that misses a number lets it through.
- Structured claims with no text, rendered from templates. This is safe but dull, and it gives up the reason to use a model at all: explaining *why* something matters.
- **Free text with references.** The Analyst writes the sentence, but every fact is a reference: `{{value:<snapshotId>}}`, `{{player:HCY-11}}`, `{{club:HCY}}`, `{{minute:61}}`, `{{score}}`. Code renders the references from the evidence.

**Choice.** Free text with references (`fourth_official_contracts.Insight`).
- **The contract** checks shape: markup is well-formed, every value referenced is cited in that claim's evidence, every claim has evidence, the text is one printable line, and provenance names the agent, prompt version and model alias.
- **The deterministic Verifier** (`services/verifier`) checks truth against the match at the moment:
  - claim text is built from an allowlist, not checked against a denylist: printable ASCII, a curated football-English vocabulary that contains no names and no number words, and capitals only for known terms and a closed set of sentence openers;
  - no club or player names are written out, in any case;
  - every player and minute referenced appears in the claim's cited events, and nothing is in the future;
  - every cited event and snapshot exists, is not after the moment, and has not been voided or restated.
- The score is rendered by code at the moment, without voided goals, so it is always right.
- The Verifier returns a `Verdict` with typed findings, which go back to the Analyst as feedback and into the provenance record.

**Consequences.**
- Numbers are correct by construction, so the Verifier's job becomes deciding what may be referenced, which it can do exactly.
- The vocabulary and opener lists are deliberately strict. An unusual word costs a retry, never a wrong publication; the Analyst's prompt asks for plain football English.
- Localisation must keep the reference set unchanged; the post-localisation check compares it.
- Whether a claim is *supported* by its evidence (no extra assertions) remains a judgement, and belongs to the LLM judge layer that runs after the deterministic checks.

---

## ADR-007: Models on Microsoft Foundry, keyless, behind aliases

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** The Analyst needs a model, and a different fallback model. Our subscription has GlobalStandard quota for gpt-5-mini (500K TPM) and gpt-4.1-mini (200K TPM) in East US 2. o4-mini is deprecating and refuses new deployments. Larger models have no quota yet; a request is pending.

**Choice.**
- **Account:** one Foundry account (`AIServices`) with one project, provisioned in Bicep (`infra/modules/foundry.bicep`).
- **Deployments:** pay-per-token **GlobalStandard**, so there is no reserved capacity.
- **Aliases:** each deployment is named for its alias, `fast` (gpt-5-mini) and `fallback` (gpt-4.1-mini). Code and provenance only ever use the alias, so swapping a model is a one-line Bicep change reviewed in a pull request.
- **Pinned versions:** `NoAutoUpgrade`.
- **Keyless:** `disableLocalAuth: true`. Agent workers will run as a dedicated `id-agents-*` identity whose only role is Azure AI User (shown as "Foundry User") on the account. The shared app identity still only pulls images.
- **Why that role:** Azure AI User grants data-plane access to the account and its projects. Calling models through the project endpoint with Agent Framework needs it. A model-only role (Cognitive Services OpenAI User) is narrower, but doesn't cover project operations or a later move to the Foundry Agent Service. It has no control-plane write rights, and key listing is inert while local auth is off.
- **Developer access:** the person running `azd` (`AZURE_PRINCIPAL_ID`) gets the same role, so live smoke tests run from a laptop. A policy test pins that this is the only assignment not to a service principal: it uses that role only, on the account only, and is granted only when a developer is named.
- **Network:** the endpoint is publicly reachable but useless without an Entra token and the role. IP allowlisting would need stable egress IPs for the container apps, and private endpoints cost more than this project warrants. Both are deliberately left for later.
- **Spending:** spend is bounded by each deployment's TPM limit (150K in total, capped at 200K by a test) and by the resource group's budget alerts.

**Consequences.**
- The fallback is a different model family, so a systematic failure of one model is less likely to repeat.
- When quota for a stronger model arrives, it becomes the `fast` or a new `quality` deployment without code changes.

## ADR-008: The matchday's spend guards live in one blob, claimed atomically

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** Starting a matchday spends model tokens, so the API refuses a start while a run is under way, during a 15-minute cooldown and beyond 24 starts a day. Those guards need to know when runs started. The API scales to zero, and a deploy briefly overlaps two revisions, so starts held in memory are forgotten or seen by only one process.

**Choice.**
- **Store:** one JSON blob (`{"starts": [...]}`, the latest 48) in a Standard LRS storage account (plan §10.4), named by `START_LEDGER_URL`.
- **Access:** keyless. Shared-key access is off, and the API's managed identity holds Storage Blob Data Contributor on the one container. The URL may carry no query, so no SAS can be configured.
- **Atomic claim:** `StartLedger.claim(started, check)` reads the starts and their ETag, runs the guards on what it read, and writes the new start only `If-Match` that ETag (or only if the blob does not exist yet). Losing the race is a `409` ("another start was recorded at the same moment"), never a second run.
- **Fail closed:** a ledger that cannot be parsed stops every start. With the Analyst configured, the API refuses to start at all without a durable ledger.

**Consequences.**
- Cost is a few blob operations per start: negligible.
- Cosmos DB (planned for state) could hold the ledger later; the `StartLedger` protocol keeps that a swap, not a rewrite.
