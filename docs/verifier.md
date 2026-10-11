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
- **Prose itself isn't fully verified.** The vocabulary keeps out names, numbers and the future tense, but ordinary verbs can still assert things the evidence doesn't show ("{{club:NGT}} reply" cited against a goal by the other side). Whether a sentence is *supported* by its evidence, with no extra assertions, is the LLM judge's job, and it runs on every insight that passes these checks.
- **Only verb and plural forms are derived.** Comparatives, adverbs and agent nouns are listed explicitly, because deriving them freely produces surnames ("hunter", "turner", "holder").

## Template fallback

When no model insight passes after its retries (and after the fallback model), `template_insight(moment, facts)` builds a plain insight from the moment's own evidence. `template_localized(...)` does the same in a partner's language, from the same phrasebook (`PHRASES` in `templates.py`): English, Spanish and German phrasing of the same references. A test checks every demo moment in all three languages. Each moment kind has one template, written only with references, so templates pass verification by construction. A test checks this for every moment on the demo matchday. Templates avoid number words ("ten men", "five minutes"), because the Verifier rightly treats those as numbers.

An insight explaining a VAR overturn may cite the goal it ruled out even after the `EVENT_VOIDED` correction has landed. Any other insight citing that goal fails with `VOIDED_EVIDENCE`, which is how the correction cascade finds published items to fix.

## Other languages

Partners read insights in their own language: Northlight Sport in English, Tribuna Austral in Spanish (es-MX), Rheinblick Sport in German (de-DE). A localised insight is checked by the same `verify()`, which picks the language from the insight's locale (`languages.py`, ADR-010).

Every language keeps the same guarantees:
- **No number written out:** no digit outside a reference, and no number word. That includes ordinals and counts such as "doblete", "primera mitad", "zweimal", "Doppelpack" and "erste Halbzeit".
- **No name written out:** any name from either squad is a `RAW_NAME`. Any capitalised word that is not a known term is an `UNVERIFIED_NAME`. Spanish allows capitals only on a closed set of sentence openers and terms such as VAR. German capitalises every noun, so it has an allowlist of football nouns (`nouns_de.txt`) and accepts compounds of them ("Ballgewinn", "Torchance", "Spielstand"). A test checks that no squad name could pass as an opener or a noun.
- **Nothing about later:**
  - Spanish: "va a", "irá", "será", "pronto", "al final", and any verb in the future tense (-rá, -rán, -remos).
  - German: "wird", "werden", "bald", "später", "nächste", "Schlusspfiff", "Endstand".
- **Printable characters of the language only:** accents, ñ, ¡¿ in Spanish; umlauts, ß and „…“ quotation marks in German.
- **"Second yellow":** accepted in every language only where the cited card was a second yellow for the player named ("segunda amarilla", "zweite Gelbe Karte").

Spanish and German have no lowercase word allowlist, because a localised insight may not add facts at all.

`verify_localized(localized, canonical, moment, facts, blocked=...)` decides whether a partner's version may air:
- **Same claims** (`CLAIMS_CHANGED`): the localised insight is a version of the canonical one, with the same claims in order and the same types and evidence. The Localizer writes text only; code copies the rest.
- **Same facts in the same roles** (`REFERENCES_CHANGED`): each claim names exactly the canonical claim's references. References of different kinds may move, because word order changes in translation. References of one kind keep their order, so two clubs, a scorer and an assist, or a before and after value can never swap. A fact added, dropped or repeated is refused. The headline may only drop one of the canonical headline's own facts. It may never add or repeat one, even a fact a claim names.
- **The language's checks:** `verify()` in the partner's language.
- **The partner's blocked topics** (`BLOCKED_TOPIC`): from its policy.
- **The graphic** (`TOO_LONG`): rendered in the partner's locale, the headline fits in 120 characters and each claim in 200, the lower third's limits.

Number words are matched by pattern as well as by list, because both languages build numerals freely. The patterns are applied after folding case, accents and ß, so "dieciseis" and "dreissig" are caught too:
- Spanish: compounds ("veinticuatro", "quinientos"), ordinals including fused forms ("decimoquinto"), and counts ("cuarteto", "un par").
- German: compounds ("dreiundzwanzig", "zweihundert"), ordinal endings ("zehnte", "dreißigste"), "-mal", counts ("Zweier", "Viererkette"), and "doppel-", "halb-" and "-hälfte".

The near and far post ("primer palo", "segundo palo") name places, so they pass, as "the final third" does in English. Two adversarial review rounds probed for bypasses; every string they found is now a test.

Some costs are accepted. Each one costs a rephrase, never a wrong claim on air:
- German "wird" is refused even where it means "becomes" ("wird schwächer"), and "gleich" even where it means "equally", because telling them from the future needs grammar.
- "Die Elf" (the team), "Halbzeit" and "primera parte" (first half) are refused as counts. German claims say "Pause", as English claims say "the break".
- An unfamiliar German compound noun is refused until it is added to the list.
- German "noch" is allowed: refusing it would refuse "noch immer" (still), so "er trifft noch" is a known gap.

## Numbers in each locale

Code formats every value for the reader's locale from CLDR data (Babel):

| | en-GB | es-MX | de-DE |
|---|---|---|---|
| Decimal | 0.28 | 0.28 | 0,28 |
| Percentage | 54% | 54% | 54 % |
| Thousands | 1,234 | 1,234 | 1.234 |
| Score | 2–1 | 2–1 | 2:1 |

Mexican Spanish writes a decimal point, as CLDR records, not the comma used in Spain. Minutes read the same everywhere: 61', 45+3'.
