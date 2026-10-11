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
- Blob versioning and 7-day soft delete make a bad write or a delete recoverable.
- **Accepted risk:** the API runs as the agents identity, which can both call the models and write the ledger, so a compromised API could spend tokens and reset its own allowance. Splitting the identities buys little while one process does both; the TPM limits and budget alerts still bound spend.
- **Accepted risk:** the Match Data MCP server has no authentication of its own. It is reachable only through the environment's internal ingress, which is checked from outside after each infrastructure change; Entra authentication is the next step if the environment ever hosts apps we do not run.

## ADR-009: Security headers, and a CSP that allows inline scripts

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** The studio web app and the API should carry the standard browser protections. The web pages are prerendered with Partial Prerendering, and Next.js streams each page's data in inline scripts.

**Choice.**
- **Web (`apps/web/src/lib/securityHeaders.ts`, every response):**
  - a CSP that allows only this origin for scripts, styles, images, fonts and connections;
  - `object-src 'none'`, `frame-ancestors 'none'`, `script-src-attr 'none'` (no inline event handlers), `base-uri` and `form-action` limited to this origin, and `upgrade-insecure-requests` in production;
  - `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, HSTS for two years, `Cross-Origin-Opener-Policy: same-origin`, and a Permissions-Policy that turns off camera, microphone, geolocation, payment and USB.
- **Scripts need `'unsafe-inline'`.** Nonces need per-request rendering, which Partial Prerendering rules out. Hashes cannot list scripts whose content varies. Subresource Integrity covers only external files. Checked in a browser, a strict `script-src 'self'` blocked every page's inline data scripts, 14 to 47 per page, and the pages never became interactive. `'unsafe-eval'` is allowed in development only.
- **API (`apps/api/src/fourth_official_api/security.py`):** a plain ASGI middleware, so event streams pass through unbuffered. It sets each header, replacing any value a route set, so only one is ever sent. Every response gets nosniff, `DENY`, `no-referrer`, HSTS and `Cross-Origin-Resource-Policy: same-origin`. JSON answers also get `default-src 'none'; frame-ancestors 'none'`. The interactive docs (`/docs`, `/redoc`) load their own assets, so they keep everything but the policy.

**Consequences.**
- The XSS risk `'unsafe-inline'` leaves is small:
  - all text, model output included, renders through React as text;
  - nothing uses raw HTML;
  - no script can load from another origin.
- If the studio ever renders per request, switch to nonces and drop `'unsafe-inline'`.

## ADR-010: Localised text keeps the guarantees, not the English vocabulary

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** Partners read insights in English, Spanish and German. The English Verifier refuses any word outside a curated allowlist, which keeps claims to ordinary football English. Building and maintaining allowlists of the same depth for Spanish and German would slow every partner without adding to what matters. What matters are the guarantees: no number stated by a model, no name written out, nothing about the future, and no fact the evidence does not hold.

**Choice.**
- **One rule set per language** (`languages.py`): characters, number words, future wording, sentence openers, and which capitalised words may stand anywhere. English keeps its lowercase allowlist; Spanish and German do not.
- **Names in German** are caught through an allowlist of football nouns and their compounds, because German capitalises every noun.
- **No added facts** is structural. A localised insight is the canonical insight with new words: the Localizer outputs text only, code copies claim types and evidence, and its references must match the canonical ones.
- **Numbers are formatted by code** from CLDR data (Babel), in the reader's locale. es-MX writes a decimal point, as CLDR records.
- **When unsure, refuse.** A refusal costs a retry or a template; a wrong publication costs trust.

**Consequences.**
- German "wird" is refused even as "becomes". An unfamiliar German compound noun is refused until it is listed. Both lists grow from measured drafts, as the English vocabulary did, never by loosening the rules on numbers and names.
- Off-topic wording in Spanish or German is not caught by vocabulary. It is screened by the partners' blocked topics now, and later by content safety and the LLM judge.

## ADR-011: Editors decide on held items through the match's own feed

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** Each partner's policy names the item kinds a human must decide on before they air: Tribuna Austral holds every insight, and all three hold recaps. Producers need to approve or reject those items while the match runs, and every screen and partner stream must see the decision at once. The demo has no sign-in (plan §10.5), and Microsoft Teams is not available in the tenant yet.

**Choice.**
- **A decision is an entry.** Approving or rejecting publishes the item's next version on the match's append-only feed: the same item id, the same words, the editor's `approval` record and the new state. Approved items are placed on air by the partner's director from the current match clock. Their label becomes "reviewed" where the policy says so: "Asistido por IA · Revisado por T. Ibarra", or no label under `label-unless-approved`. A rejection keeps the item off air and must give a one-line reason, which stays with the item.
- **The contract checks every decision.** The entry is built through `TenantItemEntry`, so an item airs only if approved, a rejection always records its reason, and a reviewed label always has its approval behind it.
- **One decision per item, for one run.** Decisions are serialised per matchday, and a new run waits for a decision under way. The second of two simultaneous decisions on the same item is refused (409). A decision names the run it was made in, and the feed refuses it if another run has started, even mid-decision (409).
- **Never against a correction.** If a correction since the hold targets an event an item's claims rest on, the item stays off air and the decision is refused (409). An editor cannot put a withdrawn fact on air.
- **Only during the match.** After full time the feed is closed and held items stay off air (410). When the partner's graphics are full that minute, the decision is refused with 503 and `Retry-After`, and the item stays held.
- **Reasons only for rejections.** A rejection must give a one-line reason (checked at the edge, 422). An approval carries none.
- **From the studio only.** `POST /api/tenants/{t}/matches/{m}/items/{id}/decision` uses the matchday start's guard: a required `X-Requested-By` header that a cross-site form cannot send, with any browser `Origin` refused. The web app's same-origin proxy is the only caller.
- **Who decided.** Without sign-in, a decision is recorded against the partner's duty editor (`dutyEditor` in its policy). This is a named demo identity, not a signed-in person. With Entra ID the editor is the signed-in user, and the endpoint then also needs authorisation per partner.

**Consequences.**
- Anyone who can reach the studio can decide on the demo's synthetic items. That is acceptable for a public, no-login demo of synthetic data. It is not acceptable for production, where sign-in and per-partner roles come first.
- Edit-and-approve (E) is not offered yet. Edited words would have to pass the Verifier again before airing, and that path is not built.
- Teams approvals (an Adaptive Card that calls the same endpoint) wait on a Microsoft 365 tenant.

## ADR-012: The corrections desk acts on every partner item, once, and reports it

**Date:** 2026-10-11 · **Status:** Accepted

**Context.** When the source data changes (a goal ruled out, a scorer reassigned), partner items already on air or held for an editor may rest on a fact that is no longer true. Each partner sets how it wants that handled (`correctionBehaviour`). The studio must be able to show that everything was found and dealt with, and how fast.

**Choice.**
- **Found by evidence.** A canonical insight is touched when its claims' evidence, or its moment's events, include the corrected event. A void does not touch the VAR moment that explains it. Each partner's latest version of a touched insight is acted on if it is on air or held.
- **Acted on by policy.**
  - A held item is pulled (`retracted`): it can never air.
  - After a void, an item on air is pulled everywhere, since the fact no longer exists.
  - After an amendment:
    - `auto-amend` airs a new version, regenerated from the corrected facts by the partner's template and verified again; it `supersedes` the old one, which becomes `amended`;
    - `escalate` holds that new version for an editor;
    - `retract-and-notify` pulls the item.
  - A new version that cannot be made, or does not verify, is pulled instead.
- **Corrected facts** are the match with the amended event added as a new version. `prepare` keeps only the latest version of an event.
- **Once per item, however the work arrives.** The desk runs when a correction is issued, and again whenever a partner's items for an insight resting on an issued correction are published later (in a fast replay, items can arrive after the correction). A record of the items acted on and the versions made keeps any item from being acted on twice, and one lock serialises the desk.
- **Reported.** Every run publishes a `correction_report`:
  - the correction and the corrected event;
  - the insights touched;
  - each partner action (`was`, `action`, `newItemId`);
  - when the desk started and how long it took.

  At issue it is published even when nothing was touched. For late items it is published only when something was done. The Corrections Center merges reports by correction.
- **Amended versions air outside the partner's pace limit.** A correction does not wait its turn.

**Consequences.**
- Regeneration uses the partner's template, not the model. It is deterministic and verifies by construction, but it is plainer than the original words. Model regeneration with re-verification can follow.
- Metric restatements (`METRIC_RESTATED`) are not handled yet. Snapshots stay as computed.
- Wall-clock timing makes a replay non-reproducible, so the desk's clocks are injectable. The recorded fixtures use fixed clocks.
