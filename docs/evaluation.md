# The Proving Ground

The Proving Ground answers one question before a prompt or model change ships: over matches where we know exactly what happened, is the change at least as safe and as good as production? It replays a seeded benchmark through the real pipeline, scores what went on air against ground truth, and the Release Gate blocks the change if it is worse where it matters (ADR-014).

```sh
uv run python -m fourth_official_proving run --config template --matches 20 --out card.json
uv run python -m fourth_official_proving gate --candidate candidate.json --baseline production.json
```

`gate` prints every rule and exits 1 when it blocks, so a CI job fails the pull request.

## Configurations

| Name | Analyst | Cost |
|---|---|---|
| `template` | The deterministic templates alone. Tests the harness itself. | None |
| `production` | Exactly what the API runs (`fourth_official_explain.production`): Analyst `v1.2` on `fast` (gpt-5-mini, minimal reasoning), then `fallback` (gpt-4.1-mini). | About $0.15 for 20 matches |
| `candidate` | Production with the Analyst's `v1.4` prompt, deliberately worse: it asks for colour, season form and players around the moment, which the Verifier refuses. It exists so the gate can be shown blocking a change. | About $0.08 for 20 matches |

Partners localise by template in every configuration: the Proving Ground judges the Analyst. A model run serves the benchmark to the Analyst's tools from a Match Data server on loopback that lives as long as the run, needs `FOUNDRY_PROJECT_ENDPOINT` (a Foundry project URL, nothing else is accepted) and an Azure sign-in that holds Azure AI User on the account, and prices every call's tokens by the model behind its alias (`PRICES_PER_MILLION`).

## In CI

`.github/workflows/proving-ground.yml` runs on any pull request that changes the pipeline, the benchmark, the Proving Ground, the dependencies or the model deployments. Two jobs run one after the other over the 20-match smoke subset (together, they share the deployments' rate limits and are refused often enough to skew the comparison): the base branch's own `production` configuration (its code, never the pull request's copy, so a pull request cannot move the bar it is judged by) and the pull request's. Both run in the same place minutes apart, so latency is compared like for like. A third job gates the candidate against that baseline and writes both scorecards' counts and the verdict to the job summary; the scorecards are kept as artifacts. A gated pull request costs about $0.30. Until the base branch has a production configuration (the bootstrap), the candidate is recorded but not gated.

The runs sign in as the proving identity (`id-proving-*`) through workload identity federation. It is trusted only for this repository's pull requests and holds Azure AI User on the one Foundry project, not the account: it cannot list the account's keys or reach another project, though within the project it can do what a project user can (manage agents and their data, read the project's connections). Narrower roles were tried and refused by the project endpoint with a bare 403: Cognitive Services OpenAI User, and a custom role with every inference data action. A model run in which no model wrote anything (every draft fell back to the template, as it does when the models refuse every call) fails as "cannot judge" rather than passing as a template run. Anyone who can push a branch here can use it, the same people who can already merge code into what the API runs. GitHub gives a fork's pull request, and Dependabot's, neither the secrets nor a token, so the jobs are skipped there. The gate is a quality check, not a security boundary: review still decides what merges.

`eval/results/production-20.json` and `candidate-20.json` are the runs recorded below, kept as evidence; the gate in CI does not read them.

## The benchmark

A hundred matches, `m1001` to `m1100`, each from its own seed (`fourth_official_simulator.benchmark`). A smaller run is the start of the full one, so the 20-match smoke subset is always the same 20 matches. Each match has a storyline planted in it, drawn from its seed:

- zero to four scripted goals;
- a red card (one match in four);
- a press that collapses in the second half (two in five);
- a goal VAR rules out after it is published (about one in three of those with goals);
- a scorer reassigned after the final whistle (about one in three).

The simulator records what really happened as ground truth, as it does for the demo matchday.

## How a run works

Each match is replayed headless, with no waiting and fixed clocks, through the same code the API runs: moment detection, the Explainer and the Verifier, all three partners' policies, and the corrections desk. Only the time spent explaining a moment is measured, because that is what a configuration changes. The runner then holds what is on air at full time against the truth: the simulator's own events with every correction applied. That is not the Verifier's view of the match. The Verifier checks a claim against what was known when it was written; the Proving Ground checks what is still on air against what is finally true, so a correction the pipeline failed to carry through shows up.

## Measures

Every measure is kept as counts (`hit` of `of`), never as a percentage, so readers compute rates the same way the gate does.

| Measure | Counted as | Target |
|---|---|---|
| Supported claims | Claims partners still air at full time, in their own words, whose references the truth supports, of all such claims. A claim fails if it rests on an event ruled out (except the VAR decision's own insight, which cites the goal it rules out), names a player not credited in its events as finally credited (the shot behind a cited goal vouches for nobody), names a minute none of its events happened in, or states a score that counted a goal later ruled out. Headlines are held to their own references. | All |
| Storyline recall | Planted goals, red cards, VAR decisions and press collapses that a published insight explains: a moment of the same kind and club, sharing an event or within 2 minutes; a collapse found within 10 minutes of it starting. A reassigned scorer is a correction and counts under corrections carried. | ≥ 85% |
| Key-moment precision | Published insights about a real moment: one shown by events (goal, big chance, red card, VAR decision), or a shift a storyline planted. An unplanted press, momentum or shape story is a false positive. | ≥ 80% |
| Verifier catch | Lies made by code from each published insight (a player who took no part, a minute still to come, a bare number, an invented name, evidence that does not exist, evidence VAR had ruled out) that the Verifier refuses. | 100% |
| Policy violations | Partner items on air at full time with a blocked topic, held for approval but aired, or disclosed other than the partner's policy says. | 0 |
| Model written | Insights a model wrote; the rest fell back to the template. | Report |
| First-attempt pass | Model-written insights that passed the Verifier first time. | Report |
| Corrections carried | Partner items resting on a corrected event, whenever they were published, that the corrections desk pulled or replaced. A version the desk remade is the replacement; the VAR decision's own insight is not counted. | All |
| Latency | Time to explain a moment, p50 and p95 (nearest rank). Not reported when no model wrote. | Report |
| Cost | Model spend for the run, in US dollars. | Report |

## The Release Gate

A candidate is compared with the production baseline over the same benchmark and is blocked if:

- any claim on air at full time is unsupported, or it put nothing on air where the baseline did;
- any partner item on air breaks its partner's policy;
- the Verifier lets any planted lie through;
- any partner item resting on a corrected event is still on air as it was;
- storyline recall drops more than 3 points;
- the share of model-written insights drops more than 5 points (a prompt the Verifier keeps refusing falls back to the template);
- the median time to explain a moment (p50) grows more than 15% and by more than 2 seconds. The plan names p95, but on the smoke subset p95 is whether a few drafts needed a retry: identical code in CI measured 13.1 s and then 20.1 s. The tail stays in the scorecard; retries show in the first-attempt pass and the model-written share.

Rates are compared exactly, as integer cross-products of their counts, and rounded only for display. `gate` exits 1 when it blocks and 2 when it cannot judge: a scorecard it cannot read (missing, over 1 MiB, not JSON, not a scorecard) or two scorecards of different benchmarks. Free text in a scorecard (claims, reasons, details) is one printable line; a page shows it as text, never as markup.

## Results

The release gate on the smoke subset, production against the `v1.4` candidate (`eval/results/production-20.json`, `eval/results/candidate-20.json`):

| Measure | Production | Candidate |
|---|---|---|
| Supported claims | 236 of 236 | 206 of 206 |
| Storyline recall | 54 of 54 | 54 of 54 |
| Model written | 78 of 79 (98.7%) | 23 of 79 (29.1%) |
| First-attempt pass | 59 of 78 | 16 of 23 |
| Latency p95 | 22.1 s | 32.3 s |
| Cost | $0.14 | $0.08 |
| **Gate** | (baseline) | **Blocked**: model written |

The Verifier kept every embellishment off air (no unsupported claim either way), so the candidate's damage shows as fallbacks to the template. Its median was faster (3.1 s against 4.9 s): fewer drafts were written by the model at all. A second production run, as a candidate against the first, was allowed: p95 within 4% and model written within 1.2 points, inside the gate's margins.

The template configuration over the full benchmark (`eval/results/template.json`):

| Measure | Result |
|---|---|
| Supported claims | 1,067 of 1,067 |
| Storyline recall | 264 of 266 (99.2%) |
| Key-moment precision | 363 of 414 (87.7%) |
| Verifier catch | 2,124 of 2,124 |
| Policy violations | 0 |
| Corrections carried | 162 of 162 |

The two storylines missed are press collapses: one found 12 minutes after it began, outside the 10-minute window (`m1076`), and one never found (`m1083`). Both are the detector's, not the harness's.
