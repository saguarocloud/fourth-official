# Verifier

The Verifier (`services/verifier`) decides whether an insight can be published. This page covers its first, deterministic layer. An LLM judge runs after it and checks that each claim is *supported* by its evidence. ADR-006 explains why claims carry references instead of raw facts.

## Claims and references

An `Insight` explains one `Moment` through up to five typed claims (`stat`, `comparison`, `causal`, `milestone`). Each claim cites events and metric snapshots as evidence. Its text never contains a raw number or name:

| Reference | Renders as | Example |
|---|---|---|
| `{{value:<snapshotId>}}` | The snapshot's value, formatted by metric: percentages for possession, field tilt and pass completion; whole numbers for counts and the chaos index; one decimal for PPDA; two otherwise | `58%`, `1.24` |
| `{{player:<playerId>}}` | The player's name | a name from the squad list |
| `{{club:<code>}}` | The club's name | `Harbour City` |
| `{{minute:<n>}}` | The minute, broadcast style | `61'` |
| `{{score}}` | The score at the moment, without voided goals | `2–1` |

`render(text, facts, as_of_seq=…)` does the substitution. It refuses to render anything it cannot resolve, so it only ever runs on verified insights.

## Checks

| Finding | Blocks |
|---|---|
| `MOMENT_MISMATCH` | An insight that is not about the moment it claims to explain |
| `BARE_NUMBER` | Digits or number words (two, dozen, twice…) in the text |
| `RAW_NAME` | A club or player name written out instead of referenced |
| `UNVERIFIED_NAME` | A capitalised word that could be an invented name. Mid-sentence, only known terms (VAR, PPDA…) pass. At the start of a sentence, only common openers do. |
| `UNKNOWN_PLAYER`, `UNKNOWN_CLUB` | A reference to someone not in this match |
| `FUTURE_MINUTE`, `FUTURE_EVIDENCE` | A minute, event or snapshot after the moment |
| `EVIDENCE_NOT_FOUND`, `SNAPSHOT_NOT_FOUND` | Evidence that does not exist |
| `VOIDED_EVIDENCE`, `SUPERSEDED_EVIDENCE` | An event voided by a correction, or a snapshot that has since been restated |
| `UNDEFINED_VALUE` | Quoting a metric that has no value (for example PPDA with no defensive actions) |

- A verdict passes only with no findings, and lists every finding (up to 64) with the claim it concerns.
- The seeded adversarial tests are wrong numbers, invented players, wrong scorelines and future leakage, and every one is blocked.

## Template fallback

When no model insight passes after its retries (and after the fallback model), `template_insight(moment, facts)` builds a plain insight from the moment's own evidence. Each moment kind has one template, written only with references, so templates pass verification by construction. A test checks this for every moment on the demo matchday. Templates avoid number words ("ten men", "five minutes"), because the Verifier rightly treats those as numbers.

An insight explaining a VAR overturn may cite the goal it ruled out even after the `EVENT_VOIDED` correction has landed. Any other insight citing that goal fails with `VOIDED_EVIDENCE`, which is how the correction cascade finds published items to fix.
