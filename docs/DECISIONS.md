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

## ADR-002: MIT licence; repository private until submission

**Date:** 2026-10-10 · **Status:** Accepted

**Context.** The Official Rules require a public repository at submission and grant Microsoft and the Premier League a broad licence to the entry. Project pages and public repositories are visible to competing entrants.

**Choice.**
- Licence: MIT.
- The repository `saguarocloud/fourth-official` stays **private** during development and is made **public before submission** (target: Oct 25–26, 2026).
- No proprietary Saguaro Cloud IP goes in the repository. Tenant and subscription IDs live in `azd env` or `.env`, which are git-ignored.

**Consequences.** CI badges and Codespaces links only work for judges once the repo is public. The submission checklist must include flipping visibility and checking every link in a private browser window.
