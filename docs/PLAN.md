# Plan

Running checklist. Update daily. Times are Mexico City.

## Phase 0: Foundations (Oct 8–9, running late)

- [x] Azure CLI signed in as the work account; Owner on the subscription
- [x] Resource providers registered
- [x] Region chosen: East US 2 (ADR-001)
- [x] GitHub repository created and public: `saguarocloud/fourth-official`; `main` protected, PRs only (ADR-002)
- [x] Stack chosen: Python 3.12 + uv, Next.js + TypeScript (ADR-003)
- [x] Deployment model chosen: Bicep + azd, infra local, apps via GitHub Actions with workload identity federation (ADR-004)
- [x] Tooling and CI pull request (api and web skeletons, quality gates) (#1)
- [ ] Infrastructure pull request (Bicep, azd, deploy identity, deploy workflow) (#3)
- [ ] Design system pull request: LED-board control room, `DESIGN.md`, Control Room screen on replay data
- [ ] Security headers on web and api (CSP, HSTS, frame-ancestors, referrer and permissions policy)
- [ ] Observability: wire Application Insights into both apps with OpenTelemetry and Entra ID auth (local auth is disabled)
- [ ] API: explicit CORS allow-list when the web app starts calling it; decide whether public `/docs` stays on for judges
- [ ] Supply chain: SBOM and image signing in the deploy workflow
- [ ] Rate limiting on public endpoints (API throttling; consider Front Door/WAF for the demo week)
- [ ] Authentication: Entra ID sign-in and app roles for admin functions; public Viewer mode stays read-only
- [ ] Open decisions settled: names and collision check, team, Teams route, brand, languages
- [x] Dev environment provisioned via `azd provision` (budget $100/month)
- [ ] Upgrade subscription to pay-as-you-go (before the credit expires around Nov 6)
- [ ] Foundry quota request for a stronger `quality` model
- [x] Simulator v0 emitting events
- [ ] Placeholder project on Innovation Studio (neutral title); teammates joined and registered (by Oct 20, 1:00 pm)
- [ ] Email hackathon support: partner credits (§4.12), how to declare a category

## Phase 1: Thin end to end (Oct 10–14)

- [x] Match event and correction contracts (ADR-005) (#7)
- [ ] TypeScript types generated from the contract schemas when the web consumes events
- [x] Simulator engine: squads, styles, possession-chain match engine, realism checks (docs/simulator.md)
- [x] Simulator storylines, ground truth and scheduled corrections; fixed demo matchday (docs/simulator.md)
- [ ] Metric restatement correction kind (demo match m44)
- [ ] Simulator 5 Hz tracking frames
- [ ] Event Hubs publisher and infrastructure
- [x] Stats engine: metrics with evidence, snapshots and windows (docs/metrics.md)
- [ ] Stats engine: restate snapshots when corrections change their events
- [x] Moment Detector: event and pressing-shift moments with evidence (docs/moments.md)
- [ ] Moment Detector: momentum swing and tactical shift rules
- [x] Verifier, deterministic layer: claim markup, rendering, adversarial checks (ADR-006, docs/verifier.md)
- [ ] Verifier, LLM judge layer (Foundry evaluation)
- [x] Analyst agent (Agent Framework on Foundry, Match Data MCP) with verification loop and fallbacks (docs/explain.md)
- [x] Match replay and live feed: moments, verified insights and corrections, served by the API (docs/replay.md)
- [ ] Deploy the Analyst: internal Match Data app, agents identity and Foundry settings on the API
- [ ] Match Live screen in the web app, fed by the stream
- [x] Match Data MCP server: read-only, time-bounded tools (docs/match-data.md)
- [ ] Match Data MCP server: Container App, Entra-authenticated ingress, Cosmos-backed store

- [ ] Simulator → Event Hubs → stats → Moment Detector → Analyst ⇄ Verifier → one tenant → Match Live UI, deployed with `azd up`
- [ ] Attend Reactor livestream (Oct 14, 10:00)
