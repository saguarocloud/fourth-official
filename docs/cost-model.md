# Cost model and operations measures

How Operations (`GET /api/operations`, the Operations screen and the Control Room's chips) measures a matchday run and what it costs. Every number is computed by code from what the platform recorded while it ran (ADR-016); nothing on screen is typed in.

## What is measured

| Measure | From | To | Notes |
|---|---|---|---|
| **Event to on air** | The replay playing the last event an insight rests on | The partner's item (first version) published on air | Items aired without an editor only. Items held for an editor wait for a person, so they are counted, not timed. |
| **Explaining** | A moment published | Its verified insight published | Includes waiting for a free slot (three moments explained at once). |
| **Corrections** | The corrections desk starting on a correction | Its report | Timed by the desk itself (`CorrectionReportEntry.elapsedMs`). |
| **Fallbacks** | Insights the template wrote | Insights published | The template steps in when every model attempt failed verification or errored. |
| **First pass** | Insights whose first model draft passed | Insights a model drafted | |
| **Verification pass rate** | Model drafts the Verifier passed | Model drafts it judged | Attempts that errored were never judged. |

Times are read from one monotonic clock per match log, in whole milliseconds. Percentiles are nearest rank over every timed item in the run, pooled across matches (never a percentile of percentiles).

## Objectives (plan §9)

| Objective | Target |
|---|---|
| Event to on air, median | ≤ 4 s |
| Event to on air, 95th percentile | ≤ 8 s |
| Corrections desk, 95th percentile | < 10 s |

Each partner is also judged against its own policy's latency budget (Rheinblick Sport's is 8 s), read from the policy book when the report is computed: the report gives the budget and how many of the partner's timed items went on air within it.

The error budget expresses the on-air objective as a share: 95 % of items aired without an editor go on air within 8 s. Each item later than that spends the budget; the report carries the counts (`late` of `of`) and the screen computes the share spent.

## Cost

**Cost of a match = model tokens × list price + the match's share of the infrastructure.**

### Model tokens

Each model attempt records the input and output tokens its calls reported (the Analyst's on the insight, the Localizer's on each partner's item). Template attempts cost nothing. A partner's cost is its Localizer's tokens; the Analyst's are shared by every partner of the match.

Prices are defined once, in `fourth_official_explain.production.PRICES`, and used by both Operations and the Proving Ground:

| Alias | Deployment | Input, per million tokens | Output, per million tokens |
|---|---|---|---|
| `fast` | gpt-5-mini (Global Standard) | $0.25 | $2.00 |
| `fallback` | gpt-4.1-mini (Global Standard) | $0.40 | $1.60 |

Money is kept in whole micro-dollars (millionths of a dollar), summed exactly and rounded once, half up.

### Infrastructure share

What the platform costs to stand, measured with Cost Management on the resource group (1–15 October 2026):

| Meter category | Cost | Why |
|---|---|---|
| Container Registry | $0.1666 a day | Basic tier, the one standing charge |
| Container Apps | $0.00 | Scale to zero, within the monthly free grant |
| Key Vault | under $0.001 | A few signing operations |
| Storage | under $0.0001 | Ledger, policy book and provenance blobs |
| Log Analytics | $0.00 | Within the daily cap |

So the infrastructure rate is **6,942 micro-dollars an hour** (`INFRA_MICROUSD_PER_HOUR`). A match's share is the rate times how long the match ran, divided by the matches of the run (the matches that have started, running or done; the matchday starts them together). Change the rate when the platform's standing charges change.

### Limits

- **A floor, not an estimate.** A call that fails before the service reports usage (a timeout) spends tokens nobody counts, and so does a localisation that fails so badly no item is published (its attempts are never on the feed).
- **Memory only.** Measures live as long as the API process. A restart, or scaling to zero, starts afresh with the next run, as the feeds do.
- **List prices.** No discounts, no commitment tiers, US dollars.
- **Within an hour.** A duration longer than an hour is reported as an hour (and logged); a match never runs that long.
- **Reports are reused for two seconds**, so a burst of requests computes the report once.

## Budget

The subscription budget is $100 a month, alerting at 25, 50, 75 and 100 % (ADR-004). The Proving Ground's gated pull requests cost about $0.30 each (`docs/evaluation.md`).
