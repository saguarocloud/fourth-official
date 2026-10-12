# Explain

The Explain stage (`services/explain`) turns a detected moment into a verified insight. A model writes; deterministic code checks every fact and has the last word.

```
moment ─▶ briefing ─▶ Analyst (fast) ─▶ Verifier ─┬─ pass ─▶ insight
                         ▲   │ findings as feedback │
                         └───┘ (twice)              └─ fail ─▶ Analyst (fallback) ─▶ … ─▶ template
```

- **Analyst** (`analyst.py`): a Microsoft Agent Framework `Agent` on Microsoft Foundry (`FoundryChatClient`, Entra ID, no keys).
  - It reads the match through the Match Data MCP server (`MCPStreamableHTTPTool`, read-only tools only), and returns an `InsightDraft` as structured output.
  - The `fast` alias (gpt-5-mini) runs with minimal reasoning effort; the `fallback` alias is gpt-4.1-mini (ADR-007).
  - A drafter is an async context manager that owns its MCP session, so the session opens and closes in the same task.
- **Held to the moment:** a per-run Agent Framework function middleware (`MomentBound`) rewrites every Match Data tool call so it cannot read past the moment being explained. This holds even during a replay, a retry or a backfill, when more of the match has been published.
- **Errors:** model and service failures are logged with their cause and recorded as `error` attempts before moving on. Programming errors (`AttributeError`, `TypeError`…) are never hidden behind a fallback.
- **Attempt budget:** at most 98 model attempts are allowed per moment, which is checked up front, so the template's attempt number always fits the insight ID.
- **Credentials:** the caller owns the Entra credential and closes it after the drafters.
- **Supply chain:** dependencies resolve to GA Agent Framework packages. One beta comes in transitively, `azure-ai-inference` (via `agent-framework-foundry`), which has no stable release yet.
- **Briefing:** every request carries the moment, its evidence events, the events just before it and the score at the moment. That is usually enough, so most drafts need no tool call. The tools remain available for metric values and older play.
- **Prompt:** versioned files with front matter (`prompts/analyst/v1.1.md`). The version is recorded in each insight's provenance.
- **Pipeline** (`pipeline.py`):
  1. Each draft is built into an `Insight`; a draft that breaks the contract gets a `MALFORMED_INSIGHT` finding that names where and why.
  2. The Verifier checks the insight (`docs/verifier.md`).
  3. On failure, the findings go back to the same model as feedback, twice.
  4. Then the next model is tried, and finally the deterministic template.
  5. A model error or timeout moves straight on to the next model.
  6. Every attempt is recorded: model, outcome, finding codes and error kind.
- **Facts:** the Verifier checks against the match as it stood at the moment, including voids in force from their VAR decisions, and snapshots computed on demand from their IDs (`ComputedSnapshots`).

## First live run

The featured demo match (m42) ran live against Foundry, through the MCP server over HTTP:
- Goals and most moments were verified within one or two attempts, in about 2–7 seconds.
- Every rendered score was correct through the VAR void: 1–1 at 78' and 2–1 at 89'.
- Every moment ended with a verified insight.

Failed drafts taught the Verifier's vocabulary and phrases, such as "final third", typographic hyphens and possessive references, with no loosening of the rules on numbers and names. The Proving Ground will measure first-attempt pass rates over many matches.

## Measuring the Analyst

`scripts/measure-analyst.py` runs the real Analyst over the demo matchday (17 moments across m42, m43 and m44), exactly as the API does, and reports the following:
- first-attempt passes;
- insights the model wrote;
- template fallbacks;
- model attempts;
- the finding codes that refused drafts.

The JSON report keeps every draft and every finding's detail for diagnosis. It spends model tokens, so it is run by hand, not in CI.

Measured on 2026-10-11, same 17 moments:

| | Prompt v1.1 | Prompt v1.2 |
|---|---|---|
| First-attempt passes | 4 (24%) | 12 (71%) |
| Written by the model | 9 | 17 (all) |
| Template fallbacks | 8 | 0 |
| Model attempts (cost) | 66 | 23 |

The gain came from the following:
- **Retries see their own draft.** A retry used to get the Verifier's findings without the draft they were about, so each retry started over and made new mistakes. Now it edits the draft it was refused for.
- **Prompt v1.2:**
  - One or two claims.
  - The only reference kinds there are.
  - Never an ID or a measure (speed, distance) in the text.
  - "Before the break" and "after the break" instead of halves.
  - A worked example.
  - How to fix a draft.
- **Verifier vocabulary:** ordinary words the model reached for (receive, opportunity, opposing, prior...). Units of measure stay out.
- **Sentence openers:** common headline words such as "Big chance". The list stays closed on purpose: ordinary words that are also surnames (Long, Young, White) never open a sentence, so a real player's name cannot pass as one.
- **"Second yellow":** a count phrase, accepted only in a claim that cites a card event that was a second yellow. Anywhere else it is still a bare number.

None of this loosened the rules on numbers, names or the future. The remaining refusals are mostly an unknown word or a club code written as text, and they are fixed on the next attempt. The `fast` model occasionally times out (20 s); the `fallback` model then writes the insight.

Production runs Analyst prompt v1.2, defined once in `fourth_official_explain.production` for both the API and the Proving Ground. Prompt v1.4 is not an improvement: it is deliberately worse (it asks for colour, season form and players around the moment) and exists only as the candidate the Release Gate is shown blocking (docs/evaluation.md). Never put it into production.

## The Localizer

The Localizer rewrites a verified canonical insight for one partner, in the partner's language and voice (`localize.py`, `localizer.py`, prompt `localizer/v1.0`). It runs on the `fast` model with minimal reasoning. It has no tools, because everything it may say is in the insight it is given.

- **It writes words only.** Its structured output is a headline and each claim's text, by claim id. Code copies each claim's type and evidence from the canonical insight, so a draft cannot cite anything new.
- **The Verifier decides.** `verify_localized` checks four things:
  - every fact survives in its role;
  - the words pass the language's rules;
  - the partner's blocked topics are avoided;
  - the text fits the lower third.
- **One retry, then the template.** A refused draft is retried once with itself and the findings, then the partner's template stands in. A timeout is retried too. Any other model error goes straight to the template, and a bug in our own code always surfaces.
- **English partners need no model.** Northlight Sport airs the canonical words, checked against its own policy. They keep the canonical provenance, because they are the Analyst's words. The check is recorded as an attempt by the localizer with no model. If the words break the partner's policy, that failed check is recorded and the template stands in.
- **If even the template breaks the partner's policy, nothing airs for that moment.** The failed attempts record why.

`scripts/measure-localizer.py` localises every demo moment for each non-English partner with the real model. Measured on 2026-10-11, from the English templates as canonical insights:

| | Tribuna Austral (es-MX) | Rheinblick Sport (de-DE) |
|---|---|---|
| First-attempt passes | 16 of 17 | 14 of 17 |
| Written by the model | 17 | 16 |
| Template fallbacks | 0 | 1 |
| Model attempts | 18 | 20 |

The first run refused mostly capitalised words: "Rote" in Rote Karte, the genitive "des Gegners", and Spanish openers such as "Casi" and "Se". These were added to the language rules without loosening those on numbers, names or the future. What remains is German "wird", refused by design, and the odd hyphenated coinage.
