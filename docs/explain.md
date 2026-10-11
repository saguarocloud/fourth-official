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
