# The Proving Ground

The Proving Ground answers one question before a prompt or model change ships: over matches where we know exactly what happened, is the change at least as safe and as good as production? It replays a seeded benchmark through the real pipeline, scores what went on air against ground truth, and the Release Gate blocks the change if it is worse where it matters (ADR-014).

```sh
uv run python -m fourth_official_proving run --config template --matches 20 --out card.json
uv run python -m fourth_official_proving gate --candidate candidate.json --baseline production.json
```

`gate` prints every rule and exits 1 when it blocks, so a CI job fails the pull request.

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
- p95 latency grows more than 15%.

Rates are compared exactly, as integer cross-products of their counts, and rounded only for display. `gate` exits 1 when it blocks and 2 when it cannot judge: a scorecard it cannot read (missing, over 1 MiB, not JSON, not a scorecard) or two scorecards of different benchmarks. Free text in a scorecard (claims, reasons, details) is one printable line; a page shows it as text, never as markup.

## Results

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
