# Plan

Running checklist. Update daily. Times are Mexico City.

## Phase 0: Foundations (Oct 8–9, running late)

- [x] Azure CLI signed in as the work account; Owner on the subscription
- [x] Resource providers registered
- [x] Region chosen: East US 2 (ADR-001)
- [x] GitHub repository created: `saguarocloud/fourth-official` (private, ADR-002)
- [ ] Open decisions settled: names and collision check, team, tech stack, budget, Teams route, brand, languages
- [ ] Budget amount set; resource groups `rg-fourth-official-dev` / `-demo` with budget alerts
- [ ] Upgrade subscription to pay-as-you-go (before the credit expires around Nov 6)
- [ ] Foundry quota request for a stronger `quality` model
- [ ] `azd auth login` for the tenant
- [ ] Repository scaffold (layout, CI, contracts, design tokens, fonts)
- [ ] Simulator v0 emitting events
- [ ] Placeholder project on Innovation Studio (neutral title); teammates joined and registered (by Oct 20, 1:00 pm)
- [ ] Email hackathon support: partner credits (§4.12), how to declare a category

## Phase 1: Thin end to end (Oct 10–14)

- [ ] Simulator → Event Hubs → stats → Moment Detector → Analyst ⇄ Verifier → one tenant → Match Live UI, deployed with `azd up`
- [ ] Attend Reactor livestream (Oct 14, 10:00)
