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

The text checks use an **allowlist, not a denylist**. A denylist of number words and name patterns can always be bypassed: by "one goal", "eleventh", a Unicode digit, or a lowercase name. Instead, claim text outside references may contain only the following:
- **Characters:** printable ASCII, plus typographic quotes and dashes.
- **Words:** words from a curated football-English vocabulary (`vocabulary.txt`), and their regular inflections. Function words and irregular forms do not inflect.
- **Capitals:** a few terms of the game (VAR, PPDA, xG), and a closed set of sentence openers ("The", "After", "With"…).

Tests guarantee that no word in the vocabulary or the openers matches a part of any squad name or of the famous-footballer blocklist, and that no number word is in the vocabulary.

| Finding | Blocks |
|---|---|
| `MOMENT_MISMATCH` | An insight that is not about the moment it claims to explain |
| `UNSUPPORTED_CHARACTER` | Anything outside printable ASCII and typographic punctuation (Unicode digits, other scripts) |
| `BARE_NUMBER` | Digits, and number or ordinal words (one, nil, eleventh, brace, twice…) |
| `RAW_NAME` | A club or player name written out, in any case, instead of referenced |
| `UNVERIFIED_NAME` | A capitalised word that is neither a term nor an allowed sentence opener |
| `UNKNOWN_WORD` | A word outside the vocabulary, such as an invented name in lowercase |
| `FUTURE_WORDING` | Wording about what happens later ("will", "eventually", "final whistle"…) |
| `UNKNOWN_PLAYER`, `UNKNOWN_CLUB` | A reference to someone not in this match |
| `PLAYER_NOT_IN_EVIDENCE`, `MINUTE_NOT_IN_EVIDENCE` | A player or minute that none of the claim's cited events shows. Headline references must be shown by some claim's events. |
| `FUTURE_MINUTE`, `FUTURE_EVIDENCE` | A minute, event or snapshot after the moment |
| `EVIDENCE_NOT_FOUND`, `SNAPSHOT_NOT_FOUND` | Evidence that does not exist |
| `VOIDED_EVIDENCE`, `SUPERSEDED_EVIDENCE` | An event voided, or a snapshot restated, at or before the moment |
| `UNDEFINED_VALUE` | Quoting a metric that has no value (for example PPDA with no defensive actions) |

- **Corrections are timed.** `MatchFacts` records the seq from which each void or restatement counts. Nothing is known before it happened, so a later VAR decision never rewrites the score shown for an earlier moment. Retracting items that were true when published is the correction cascade's job, not the Verifier's.
- **Feedback is sanitised.** A verdict passes only with no findings, and lists every finding (up to 64) with the claim it concerns. Finding details quote at most three short ASCII words from the claim, because they go back to the Analyst as feedback and into the evidence drawer, where the UI must render them as text.
- **Rendering re-checks.** `render(text, facts, as_of_seq=…, cited=…)` renders only cited snapshots from before the moment, and raises `RenderError` for anything it cannot resolve. `render_insight(insight, facts)` renders a whole insight from its own evidence.
- **Prose itself isn't verified.** Whether a sentence is *supported* by its evidence, with no extra assertions, is the LLM judge's job.

## Template fallback

When no model insight passes after its retries (and after the fallback model), `template_insight(moment, facts)` builds a plain insight from the moment's own evidence. Each moment kind has one template, written only with references, so templates pass verification by construction. A test checks this for every moment on the demo matchday. Templates avoid number words ("ten men", "five minutes"), because the Verifier rightly treats those as numbers.

An insight explaining a VAR overturn may cite the goal it ruled out even after the `EVENT_VOIDED` correction has landed. Any other insight citing that goal fails with `VOIDED_EVIDENCE`, which is how the correction cascade finds published items to fix.
