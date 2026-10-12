---
name: Fourth Official
description: The matchday control room, spoken in the language of the fourth official's LED board.
colors:
  panel-0: "#07090b"
  panel-1: "#0d1013"
  panel-2: "#151a1e"
  panel-3: "#1c2227"
  hairline: "#20272d"
  hairline-strong: "#2d363e"
  ink-1: "#e9edf0"
  ink-2: "#a1abb4"
  ink-3: "#7c8791"
  led-green: "#3ee07f"
  led-red: "#ff4a3d"
  led-amber: "#ffb43a"
  led-violet: "#bc9dff"
  led-blue: "#63b4ff"
  led-white: "#f2f5f7"
  led-off: "rgb(255 255 255 / 0.07)"
typography:
  headline:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  stat:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    fontFeature: "tnum"
  body:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
  body-dense:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Geist, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    letterSpacing: "0.08em"
  mono:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.6875rem"
    fontWeight: 400
  graphics:
    fontFamily: "Barlow Condensed, Geist, sans-serif"
    fontWeight: 700
    fontStyle: "normal | italic"
rounded:
  key: "2px"
  lamp: "999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "24px"
  "6": "32px"
components:
  key-default:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.ink-1}"
    rounded: "{rounded.key}"
    padding: "0 16px"
    height: "36px"
  key-default-hover:
    backgroundColor: "{colors.panel-3}"
  key-primary:
    backgroundColor: "{colors.led-white}"
    textColor: "{colors.panel-0}"
    rounded: "{rounded.key}"
    padding: "0 16px"
    height: "36px"
  key-danger:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.led-red}"
    rounded: "{rounded.key}"
    height: "36px"
  key-quiet:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.key}"
    height: "36px"
  key-sm:
    rounded: "{rounded.key}"
    padding: "0 12px"
    height: "28px"
  ai-tag:
    textColor: "{colors.led-blue}"
    rounded: "{rounded.key}"
    padding: "0 6px"
    height: "18px"
  board-panel:
    backgroundColor: "{colors.panel-1}"
    rounded: "{rounded.key}"
    padding: "24px"
  led-field:
    backgroundColor: "{colors.panel-0}"
    rounded: "{rounded.key}"
    padding: "16px 24px"
  nav-item:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.key}"
    padding: "0 12px"
    height: "36px"
  nav-item-current:
    backgroundColor: "{colors.panel-3}"
    textColor: "{colors.ink-1}"
  tally-lamp:
    rounded: "{rounded.lamp}"
    size: "10px"
  match-key:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.key}"
    padding: "0 12px"
    height: "36px"
  match-key-current:
    backgroundColor: "{colors.panel-3}"
    textColor: "{colors.ink-1}"
  live-board:
    backgroundColor: "{colors.panel-1}"
    rounded: "{rounded.key}"
    padding: "32px"
  live-wire:
    backgroundColor: "{colors.panel-1}"
    rounded: "{rounded.key}"
    padding: "24px 32px"
  correction-strap:
    backgroundColor: "{colors.panel-0}"
    textColor: "{colors.ink-1}"
    rounded: "{rounded.key}"
    padding: "8px 12px"
  partner-key:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.key}"
    padding: "0 12px 0 8px"
    height: "40px"
  partner-key-current:
    backgroundColor: "{colors.panel-3}"
    textColor: "{colors.ink-1}"
  key-cap:
    backgroundColor: "{colors.panel-0}"
    textColor: "{colors.ink-3}"
    rounded: "{rounded.key}"
    padding: "0 4px"
    height: "18px"
  program-monitor:
    backgroundColor: "{colors.panel-1}"
    rounded: "{rounded.key}"
    padding: "12px"
  ticket:
    backgroundColor: "{colors.panel-1}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.key}"
    padding: "8px 12px"
  ticket-current:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.ink-1}"
  reject-form:
    backgroundColor: "{colors.panel-1}"
    rounded: "{rounded.key}"
    padding: "16px"
  incident:
    backgroundColor: "{colors.panel-1}"
    textColor: "{colors.ink-1}"
    rounded: "{rounded.key}"
    padding: "24px"
  impact-fan:
    backgroundColor: "{colors.panel-0}"
    rounded: "{rounded.key}"
    width: "100%"
  item-board:
    backgroundColor: "{colors.panel-1}"
    rounded: "{rounded.key}"
    padding: "16px"
  item-board-panel:
    backgroundColor: "{colors.panel-0}"
    rounded: "{rounded.key}"
    padding: "12px"
---

# Design System: Fourth Official

## Overview

**Creative North Star: "The Fourth Official's Board"**

The control room speaks the fourth official's language: the LED substitution board. Lit 5x7 dot-matrix numerals sit on a black panel field, and state is the board's red, green and amber light. Everything else is anodised near-black hardware: panels joined by hairlines, square-cut keys, round lamps, silk-screened uppercase labels. It is built for a dark production gallery at 1440 to 1920 wide, read in glances between other monitors.

Density is high but ordered. Each screen leads with one verdict line an executive can read in five seconds, then a wall of match boards an operator scans for lamps, tallies and counts. Colour is never decoration: it appears only as signal light, so a lit dot always means something.

The system refuses the generic dark SaaS dashboard: rounded-card soup, glowing charts, gradients, coloured accents used for brand or emphasis.

**Key Characteristics:**
- Near-black anodised panels, flat, joined by 1px hairlines.
- 5x7 dot-matrix LED readouts with faint unlit dots for scorelines and clocks.
- Colour only as signal light: one colour, one icon and one label per state.
- Square-cut 2px keys; perfectly round lamps.
- Geist for UI text with tabular figures; Geist Mono only on key caps; Barlow Condensed only inside the Broadcast Preview monitor.

## Colors

A neutral black chrome with six signal lights; the lights are the only chroma on screen.

### Primary
- **Board white** (led-white): lit LED dots for scorelines and clocks, the primary key's face, and the focus ring. Clocks and scorelines are always white, never a state colour.

### Secondary (signal lights; each state owns one)
- **Verified green** (led-green): published, IN panel, within SLO, the lit lamp on the current nav item.
- **On-air red** (led-red): on air (tally and state), retracted, OUT panel, SLO breach, danger key.
- **Pending amber** (led-amber): pending approval, non-zero pending or correction counts, an amber verdict.
- **Amended violet** (led-violet): amended items only.

### Tertiary
- **AI blue** (led-blue): the AI disclosure tag and nothing else.

### Neutral
- **Gallery black** (panel-0): page background and the LED field behind every readout.
- **Panel** (panel-1): top bar, nav rail, live rail, match boards.
- **Raised key** (panel-2): default key face, row hover, nav hover.
- **Pressed key** (panel-3): key hover, current nav item.
- **Hairline / strong hairline** (hairline, hairline-strong): all dividers and borders; strong for key edges and table heads.
- **Ink 1 / 2 / 3** (ink-1, ink-2, ink-3): primary text (15.8:1), secondary text and labels (7.6:1), tertiary and disabled (4.6:1), all on panel-1.
- **Unlit dot** (led-off): the faint dots of a readout that are not lit.

### Named Rules
**The Signal Light Rule.** Colour appears only as signal light. Green, red, amber and violet mean item or system state; if nothing has that state, the colour is absent. Never use them for brand, emphasis, charts or links.

**The State Vocabulary Rule.** Each item state has exactly one colour, one icon and one label, identical on every screen, and is never shown by colour alone:

| State | Colour | Icon (Lucide) | Label |
|---|---|---|---|
| on_air | red | Radio | On air |
| published | green | CircleCheck | Published |
| pending_approval | amber | Hourglass | Pending approval |
| retracted | red | CircleSlash | Retracted (text struck through in red) |
| amended | violet | PenLine | Amended |
| dropped | ink-3 / ink-2 | CircleDashed | Dropped |
| queued | ink-3 / ink-2 | Clock3 | Queued |

**The One Blue Rule.** Blue is reserved for the AI tag. Nothing else is blue.

**The White Clock Rule.** Clocks and scorelines are lit white. A number becomes a state colour only when it is itself a state (a pending count, an SLO breach, a Proving Ground figure that breaches its gate rule, lit red; a figure that passes stays ink-1, never green).

### Partner looks (Broadcast Preview monitor only)
Each partner's graphics are drawn in its own look, inside the 16:9 stage and nowhere else. These colours are graphics, not signals.
- **Northlight Sport** (NLS, English, en-GB): navy panel #0E1A2B, aurora green accent #3DDC97 with navy ink on it; sentence case. Strap: green with navy ink.
- **Tribuna Austral** (TRA, Spanish, es-MX): panel #1C120C, orange accent #FF7A1A with #1C120C ink on it; the lower-third headline, strap lead and score bug set italic uppercase. Strap: orange with #1C120C ink.
- **Rheinblick Sport** (RHB, German, de-DE): stone panel #F1ECE3, ink #13232C; a 10-unit copper #B5552A rule on the headline and a copper score; formal weight (headline 600). Strap: copper with white ink.

**The Stage Rule.** Partner colours live inside the monitor's stage only, never in the chrome. Around the frame the board's palette and signal lights apply unchanged; inside it, no partner colour means state.

### Paper (Verify page only)
The board's light twin, for readers outside the gallery (a viewer, a journalist, a regulator holding a graphic). `[data-theme="paper"]` redefines the same tokens, so hairlines, keys, lamps and the seal are unchanged; only the ink and stone change (`color-scheme: light`).
- **Stone:** panel-0 #efebe2 (page), panel-1 #fbf9f4 (the sheet: masthead and record), panel-2 #f1ede4, panel-3 #e5e0d4; hairline #ddd6c8, strong #c2b9a7.
- **Ink:** ink-1 #14181b, ink-2 #454d54, ink-3 #626b73 (5.16:1). led-white becomes ink-1, so the primary key and focus ring print black (`0 0 0 2px panel-1, 0 0 0 4px ink-1`); led-off is 6% black.
- **Signals, darkened to keep 4.5:1 on the sheet** (on panel-1): amber #8a5600 (5.85), green #0d7339 (5.66), red #b8251a (6.02), blue #1b58b3 (6.45), violet #643cb8 (6.93). Same meanings, same one-colour-per-state.
- **Brand mark:** stays a black board, lit (#0d1013 frame, red and green rows), on paper too: the mark is the board itself.

**The Paper Rule.** Paper is for the public Verify page only. The control room is never light, and no control-room screen sets `data-theme="paper"`.

## Typography

**Display font:** none; the LED readout takes the display role.
**Body font:** Geist (with system-ui, sans-serif)
**Mono font:** Geist Mono (with ui-monospace), reserved for code, IDs and measurement; not used as a costume.
**Graphics font:** Barlow Condensed 500 to 700, with italic (`--font-graphics`, falling back to Geist), the condensed broadcast face for lower thirds, straps and score bugs. Used inside the Broadcast Preview monitor only; the chrome never sets it.

**Character:** Geist is neutral and engineered, so the dot-matrix readouts carry all the personality. Every number uses tabular figures (`time`, `dd`, `.tabular`, stat values, table numerics) so live values never shift the layout.

### Hierarchy
- **Headline** (600, 24px, -0.02em): screen title, e.g. "Control Room"; never wraps.
- **Verdict** (500, 16px, ink-1): the matchday verdict line under the header, led by a 12px round lamp.
- **Title** (600, 16px, -0.01em): product name in the top bar; top-bar readout values.
- **Stat** (600, 20px, tabular): match board counts.
- **Body** (400, 14px, 1.45): default text.
- **Body dense** (400, 13px): nav, tables, activity, state labels, captions.
- **Label** (600, 11px, 0.08em, uppercase): panel headings (silk-screened hardware labels, used as real headings, not kickers), table captions, tally text, OUT/IN labels, state labels inside the activity log.

### Named Rules
**The Silk-screen Rule.** Uppercase only at 11px with 0.08em tracking, and only for hardware labels. Sentence case everywhere else.

## Layout

The shell is a three-column grid: top bar across, nav rail left, main wall centre, live rail right (`232px | 1fr | 360px`). A screen without a live rail gives the rail's column to main (`data-rail="none"` on the shell, from 1024 up), so no empty column sits beside it. The top bar holds identity (mark, product, studio, replay label), hairline-separated readouts (event-to-air p95 vs SLO, pending approvals, corrections, cost so far) and the LED studio clock at the far right.

The main wall leads with the page header and verdict, then the match wall: a two-column grid with 16px gaps where the featured match spans both columns and carries the largest board; other boards sit two across below. The live rail holds the latest correction as an OUT/IN board above the activity log.

**Match Live** (`/match`) uses the same shell with the corrections in the live rail. The main column runs, top to bottom: page header (title, "Home v Away · Meridian League", verdict line); a controls row (`.match-live__controls`, flex, wraps, `--space-3` by `--space-4` gaps) with the match keys left and the start key right; the LED scoreboard; the minute-by-minute wire; the synthetic-data footnote. The scoreboard is one column: the scoreline field on top, a names row beneath it with each club's name under its code (the row spans the scoreline's own width, `calc(var(--scoreline-max) + 2 * var(--space-5))`), then a centred clock row (LED clock, broadcast minute, run-state lamp). The scoreline is capped at `--scoreline-max: 44rem` so the wire still shows beneath the board on a wide screen. Below 768 the board and wire pad `--space-4`, wire items drop to one column with minute and kind on one baseline, and the start key aligns left; because the rail then falls below the wire, the header shows a jump link ("2 corrections" with a Lucide ArrowDown) to `#corrections-heading`, hidden at wider widths.

**Broadcast Preview** (`/preview`) has no live rail, so main takes the full width. The first viewport runs: page header (title, "Home v Away · Meridian League", verdict line naming who holds items: "N moments in three voices: M graphics cleared for air, K pending approval at Tribuna Austral", or "across N partners" when more than one); a controls row (`.preview__controls`, flex, wraps, space-between) with the match keys left and the partner keys right; the program monitor at full width with its small keys beneath (Safe areas, Back to program); the rundown beneath the monitor. From 1800 up the rundown sits beside the monitor (`minmax(0, 1fr) minmax(44rem, 1fr)`, aligned to the top) and the monitor is sticky (`top: --space-4`), so the frame stays in view while the rundown scrolls. A reconnecting stream shows the amber notice line above the desk; the synthetic-data footnote closes the page.

- **Keyboard:** 1, 2 and 3 put a partner on the monitor; G toggles the safe-area guides; Esc returns from a previewed row to program. Keys are ignored while typing in a field and when Alt, Ctrl or Meta is held.
- **Phones (720 and below):** the partner keys become a three-up grid reading cap and partner code (name for screen readers, language dropped; the monitor bar names it); the monitor bar stays on one line, the partner name truncates and the locale hides; rundown rows become cards, each partner cell labelled by its code; the table keeps explicit `role`s (`rowgroup`, `row`, `cell`, `rowheader`) so its semantics survive the restyle.

**Approvals** (`/approvals`) has no live rail, so main takes the full width. One held item owns the desk, read against English, the next one a key away; it is not an inbox table. The first viewport runs: page header (title, "Home v Away · Meridian League", verdict line); the controls row (`.approvals__controls`) with the match keys; a message line (`aria-live="polite"`, 13px ink-1, its height reserved so a message never moves the desk) naming the item just decided (Approved "headline". It airs from the match clock. / Rejected "headline". It stays off air.) or the refusal; then the floor (`.approvals__floor`): the call sheet of waiting tickets at the left (`18rem | minmax(0, 1fr)` from 1280, stacking above the desk below it) and the desk beside it; the decisions log beneath the floor; the synthetic-data footnote, which says decisions are recorded against each partner's duty editor, a named demo identity.
- **Verdict** (phase-aware, how many wait and since which match minute): "Loading the matchday." (neutral); "This match has not started. Start the matchday from Match Live." (neutral); while running, amber "N items wait for an editor; the oldest since 61'." or "Nothing waits for an editor. N decisions this match." (green once anything is decided, neutral otherwise); at full time, neutral "Full time. N held items stayed off air." or "Full time. Nothing waits for an editor; N decisions this match."; red "This match's replay stopped. Held items stay off air." and red "The match service is unavailable. Retrying every few seconds."
- **Call sheet:** the "Waiting" panel heading with its count in tabular figures; beside it, only when two or more wait, the small K Previous and J Next keys (each disabled at its end of the queue). Tickets run oldest first, one per item, the one on the desk current. Empty, a dashed panel says "Nothing waits. Items a partner's policy holds for an editor appear here as the match runs." (at full time, "Full time. Nothing more will be held this match.").
- **Desk** (`7fr | 5fr` from 1280: the stage left spanning two rows, the reading, keys and reject form right; one column below): the item on its partner's stage, the program monitor in preview without guides, its stage label saying the words are on the desk as text; "In English" (the English partner's version of the same moment) or, when there is none, "As written", each a panel-1 panel with the headline (16px, 600, ink-1) over the claims (14px, ink-2) in the item's own `lang`; "Why it waits": the partner's policy reason ("Tribuna Austral's policy sends every insight to an editor before it airs."), the evidence count and that it was checked twice ("It rests on 3 match events, checked twice: once in English, then in Spanish."), and, when a correction has since changed its facts, an ink-1 line led by an 8px red lamp saying it cannot air and should be rejected with the correction as the reason; the keys (primary "A Approve as T. Ibarra", default "R Reject…" with `aria-expanded`); the duty-editor line in 11px ink-3 ("T. Ibarra is Tribuna Austral's duty editor (demo identity): this demo has no sign-in."); the reject form when open. A visually hidden `h2` ("Partner: headline", `tabindex="-1"`) heads the desk and takes focus when a new item arrives. An item from a partner the studio does not know shows a dashed panel saying it cannot be decided here.
- **Empty floor:** with nothing on the desk the floor drops to one column (`data-empty`), so the call sheet spans the floor rather than sitting as one narrow box.
- **Keyboard:** A approves; R rejects, opening a one-line reason (prefilled "A correction changed this item's facts" for a corrected item); Esc cancels the reason (a visible Esc key cap on Cancel); J and K move down and up the queue. Shortcuts ignore key repeat, Shift, Alt, Ctrl and Meta, IME composition and typing in a field, and the keystroke is spent on the shortcut (R never also types into the reason it opens). E (edit and approve) is not offered: edited words would have to pass the Verifier again.
- **Safety:** after the desk shows a different item its keys and buttons wait 600ms (`SETTLE_MS`), so no decision lands on an item the editor has not had time to see. They also wait while a request is in flight, outside a running match and before the run is known. An item decided here leaves the queue at once, before the feed confirms it. When the item on the desk is decided elsewhere, the desk keeps its place, shows the item that took it, and the message line says so ("headline" was decided elsewhere, then either "The next item is on the desk." or "Nothing else waits."). A corrected item can only be rejected: Approve is disabled and A does nothing.
- **Focus:** after a decision, to the new item's desk heading; after Cancel, back to the R key; to the "Waiting" heading when the queue empties.
- **Phones (720 and below):** the decisions log becomes cards, each column a labelled line (see Decisions log).

**Corrections** (`/corrections`) has no live rail, so main takes the full width. A correction is a substitution: every partner item it reached is shown OUT and IN, never as a log table of affected ids. The first viewport runs: page header (title, "Home v Away · Meridian League", verdict line); the controls row (`.corrections__controls`) with the match keys (the featured match when none is asked for); the correction keys; the incident panel; "What it reached" with the impact fan and the item boards beneath; the synthetic-data footnote, which says the corrections desk finds every partner item resting on the corrected event and acts as each partner's policy says.
- **Verdict:** "N corrections this match: M partner items corrected across P partners and L languages." Green when nothing waits; amber, with "; K new versions held for an editor" before the full stop, when escalated versions wait for an editor. With no corrections, neutral: "No corrections this match. When the source data changes, every item it reached appears here." Neutral "Loading the matchday." while matches load; red "The match service is unavailable. Retrying every few seconds."
- **Correction keys:** a group labelled by the "Corrections this match" panel heading, sitting on one row with its keys (wraps, `--space-2` by `--space-3` gaps): one default key per correction, in issue order, reading `Kind: OUT → IN` ("Ruled out: 2-1 → 1-1", "Amended: …"). The current key is `aria-pressed`: panel-3, ink-3 edge, no bevel, like a pressed key. The screen opens on the correction that reached the most partner items, the earliest on a tie; choosing another key resets Replay. Switching match starts afresh.
- **Incident** (`.incident`): a panel-1 panel padded 24px with a hairline edge. An `h2` with the correction's summary (20px, 600, ink-1); then the body, one column, `3fr | 2fr` from 1280: the OUT/IN board in brief form (no summary or UTC time in its caption, only "N published items corrected.", counting only items that were on air, or "No published item rested on it.") beside a facts `dl` in two columns (11px uppercase ink-3 terms over 14px ink-1 values): Correction ("Event voided" / "Event amended"), Corrected event (its id, tabular), Issued (studio time, `Europe/London`, hh:mm:ss, matching the top-bar clock), Desk reports (how many reports the desk published for it). Last, above a hairline, the summary bar: "3 partner items (2 on air, 1 held) · 3 partners · 3 languages · 4 ms" at 24px weight 600, tabular, ink-1, prefixed for screen readers by "What it reached:"; the held split appears only when something was held; before the desk reports, "The corrections desk has not reported yet."
- **Desk time:** milliseconds under a second ("4 ms"), seconds to one decimal above ("6.4 s"), summed over the correction's reports.
- **What it reached:** the panel heading with the small Replay key at the right (shown only when items were reached); the impact fan; then the item boards as a list labelled "Items corrected", one column, `repeat(auto-fill, minmax(28rem, 1fr))` from 1280. With nothing reached, a 13px ink-2 sentence: "No partner item rested on the corrected event." (or, before any report, "The corrections desk has not reported on this correction yet.").
- **Phones (720 and below):** the fan switches to its stacked layout (a 400-unit viewBox read top to bottom: the correction, its insights, then each partner item), so every node stays legible without scrolling; the wide layout hides, and a hidden layout is out of the accessibility tree, so the fan is announced once; each board's OUT and IN panels stack; the facts drop to one column; the summary bar drops to 20px.

**Provenance** (`/provenance`) has no live rail, so main takes the full width. An item's signed record, read as the item annotated, not as a table of hashes. The first viewport runs: page header (title, "Home v Away · Meridian League", verdict line); the controls row (`.provenance__controls`) with the match keys; then the picker and the record, `20rem | minmax(0, 1fr)` from 1024 with the picker sticky (`top: --space-4`, at most the viewport tall), stacked below 1024 (picker at most 22rem tall, 15rem on phones, scrolling inside). Under the record, a 13px ink-2 link, underlined in strong hairline, with a trailing ArrowRight: "Open the public verification page" (`/verify/[itemId]`). The synthetic-data footnote closes the page.
- **Verdict:** leads with the match count, then the chosen record's state: green "N partner items on record for this match. This one is signed and unchanged."; amber "… This one is unchanged but signed with a development key."; red "This record does not verify: reason."; amber when the item has no record yet or it could not be read; neutral "No partner item is on record for this match yet. Each one is signed as it is published." and "Loading the matchday."; red "The match service is unavailable. Retrying every few seconds."
- **Choosing an item** links to `?match=…&item=…#record`, so the record scrolls into view (`scroll-margin-top: --space-4`) and keeps the address shareable.
- **Not on record:** a panel-1 note (65ch, ink-2) in place of the record ("No record has been issued for this item yet…", or that it could not be read, with a small "Try again" key when busy or unavailable).

**Verify** (`/verify/[itemId]`) is the public page, standalone: no shell, no nav, in Paper. A panel-1 masthead with a hairline foot holds the brand mark and "Meridian League Studios · Fourth Official" (the product in ink-2), aligned to the record's 64rem column so the mark sits over the record's left edge. Main (64rem, centred, 32px by 16px padding) runs: a small title, "The studio's record of this graphic" (16px, 500, ink-2; the seal is the answer, so it is set larger than the title); the record in an `aria-live="polite"` region (or the note: "Checking the record.", "The studio has no record of this graphic.", busy, unavailable with "Try again"); "How this check works" (65ch, two ink-2 paragraphs: what is signed, and that a copied graphic can sit beside a genuine id, so the words must match too); a 13px ink-3 synthetic-data footer. The page is `noindex`.

**Proving Ground** (`/proving-ground`) has no live rail, so main takes the full width. The Release Gate's last call on a candidate, made as a go/no-go poll rule by rule; never a dashboard of metric cards or a bare pass/fail badge. It reads the recorded runs (production and the candidate on the smoke subset, the template over the full benchmark) and the gate's verdict on them. The page runs: page header (title, verdict line); the poll board, one column, `minmax(20rem, 26rem) | minmax(0, 1fr)` from 1280 with The call left and The poll right (aligned to the top); "Side by side", capped at 64rem, a 13px ink-3 note ("Every measure of both runs. A measure marked (reported) is shown for context: the gate does not rule on it.") over the data table; then Unsupported claims beside The full benchmark (`3fr | 2fr` from 1024), stacked full width when there are no failures (the benchmark then capped at 64rem); the synthetic-data footnote at 75ch, which says every pull request runs its production configuration beside the base branch's on the same N benchmark matches, and that the candidate is a prompt kept deliberately worse.
- **Verdict:** red "The Release Gate blocks Analyst prompt v1.4 against production's v1.2 on N of 7 rules: rule title, candidate figure against production's (allowance); …." naming every no-go rule; green "The Release Gate allows …: all 7 rules call go."; neutral "Reading the recorded runs."; red "The recorded runs could not be read: the match service did not answer." and red "Too many reads from here. Wait a moment and try again.", both with a small "Try again" key beneath the header.
- **Phones (720 and below):** each poll station puts lamp and call, title and figure on one line (`auto | 1fr | auto`), production and the rule wrapping beneath at full width; padding 16px.

Spacing runs on a 4px base (4, 8, 12, 16, 24, 32). Main padding is 24px by 32px; boards pad 24px (featured 32px); rail sections are separated by 32px.

Breakpoints:
- **1440 and up:** `232 | 1fr | 360`.
- **1280 to 1439:** `208 | 1fr | 320`; readout padding tightens to 12px.
- **1024 to 1279:** nav collapses to a 64px icon rail (labels kept for screen readers), `64 | 1fr | 300`; the featured board stacks to a single column.
- **Below 1024:** everything stacks (top, nav as a horizontal icon strip with 40x44 targets, main, rail); top-bar readouts become a two-column grid; main padding 16px.
- **Below 768:** the match wall goes to one column; stats go two across.
- **Broadcast Preview only:** 1800 and up puts the rundown beside the monitor; 720 and below is the phone layout above.
- **Approvals only:** 1280 and up puts the call sheet beside the desk and the stage beside the reading; 720 and below turns the decisions log into cards.
- **Corrections only:** 1280 and up puts the incident's facts beside its board and lays item boards out at `minmax(28rem, 1fr)`; 720 and below stacks each board's panels and the facts, and the fan switches to its stacked layout.
- **Provenance only:** 1024 and up puts the sticky picker beside the record; 768 and up sets each claim's margin note beside it; 1280 and up puts the life beside the facts; 720 and below caps the picker at 15rem and pads the record 16px.
- **Proving Ground only:** 1280 and up puts The call beside The poll; 1024 and up puts Unsupported claims beside the benchmark (when there are any); 720 and below folds each station to one line.

No layout shift as live data arrives: fixed-width LED glyphs and tabular figures hold every width.

## Elevation & Depth

Flat. There are no drop shadows and no glow. Depth comes from tonal layering of the panel blacks (panel-0 page and LED field, panel-1 panels, panel-2/3 keys) and 1px hairlines. Readouts sit in a recessed panel-0 field inside a panel-1 board, like the physical LED panel set into its housing.

### Shadow Vocabulary
- **Key bevel** (`box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.05)`): a 1px top highlight on default keys; removed on press.
- **Focus ring** (`box-shadow: 0 0 0 2px #07090b, 0 0 0 4px #f2f5f7`): the only outer ring, on every focusable element (`a`, `button`, `summary`, `[tabindex]` on `:focus-visible`, with a transparent 2px outline for forced-colours mode).

### Named Rules
**The No-Glow Rule.** Lit things are lit by colour, not by blur or bloom. No glow shadows, no gradients behind readouts or charts. The one sanctioned exception is the lit tally lamp's small specular highlight (a radial gradient from #ff8a80 into led-red), which models a physical bulb.

## Shapes

Two shapes only. Hardware is square-cut with a 2px radius: keys, boards, LED fields, nav items, AI tag, key caps. Lights are perfect circles (999px): tally lamps (10px), verdict lamp (12px), current-nav lamp (6px), and every LED dot. Borders are 1px hairlines. Never an outlined square for a lamp, which reads as a checkbox.

## Components

### Buttons (key buttons)
A square-cut hardware key, as on a vision mixer; the primary key is the lit one.
- **Shape:** 2px radius; 36px tall (28px small); 16px side padding (12px small); 13px, weight 500.
- **Default:** panel-2 face, strong hairline edge, 1px inset top bevel.
- **Primary:** led-white face, panel-0 text; hover goes pure white.
- **Danger:** red text on a red-tinted edge. **Quiet:** transparent, ink-2.
- **Hover / Active:** hover moves to panel-3; press translates 1px down and drops the bevel (160ms, ease-out).
- **Shortcuts:** every shortcut has a visible key cap and `aria-keyshortcuts`, shipped together with the handler, never one without the other. Broadcast Preview has 1/2/3, G and Esc; Approvals has A, R, Esc, J and K.
- **Loading / Disabled:** spinner and `aria-busy`; disabled at 50% opacity.
- **Label:** the key's content sits in an inline-flex, `--space-2`-gapped, `white-space: nowrap` span (`.key > span`), so an icon and label never wrap apart.

### Chips (AI tag)
- **Style:** 18px tall, 1px blue border at 60%, blue 10px bold tracked "AI", 2px radius. Shown wherever model-written content appears. It is the only blue element.

### Cards / Containers (match board)
- **Corner style:** 2px.
- **Background:** panel-1 with a 1px hairline; the scoreline sits in a recessed panel-0 field.
- **Shadow strategy:** none (see Elevation).
- **Internal padding:** 24px; featured 32px with a two-column interior (names and clock left, partner tally list right).
- **Contents, in order:** LED scoreline (club code, score, club code on one line), club names, LED match clock with broadcast minute (`61'`, `90+3'`), partner tallies, and a stats strip (items per minute, pending approvals, corrections, p95 against SLO) divided by hairlines. Non-zero pending and corrections go amber; p95 outside SLO goes red with the label "p95, outside SLO".

### Navigation (nav rail)
- 36px items, 13px ink-2, 18px icons, 2px radius. Hover: panel-2, ink-1. Current: panel-3, ink-1, weight 500, plus a 6px green lamp at the right edge, like a lit switcher key. Unavailable screens sit in ink-3. Collapses to icons below 1280 and to a horizontal strip below 1024.

### Status lamp
The state vocabulary in one component: 16px Lucide icon in the state colour plus the label (or the label for screen readers only in compact use). In the activity log the label is also tinted and set as an 11px uppercase label with a 14px icon.

### Tally light
Broadcast tally per partner: a 10px round lamp plus "On air" (red, lit) or "Off" (ink-3, unlit lamp at 12% white). Announced as "Partner: on air/off air".

### LED readout (signature)
The fourth official's dot matrix, drawn as SVG: all unlit dots in one path and all lit dots in another (two nodes per readout, whatever its length).
- **Glyphs:** 5x7, digits, A to Z and match marks (`: . , + - ' % / $`); unknown characters fall back to `?`.
- **Spacing:** 1-dot gap between dots and one blank column between characters; every character has the same width, so a ticking clock never changes size.
- **Dot size:** whole CSS pixels only (2 to 6) so dots stay on the pixel grid. Clocks use 3px; the OUT/IN board 4px; scorelines 6px.
- **Unlit dots:** always drawn faintly (led-off), so the readout keeps its shape when values change.
- **Scorelines scale fluidly:** the scoreline fills its field width (max 26rem on standard boards, 60rem on the featured board), so the featured match reads largest on the wall. On Match Live it is capped at `--scoreline-max` (44rem).
- **Tones:** white by default; green, red, amber, violet, blue available, used by the state rules above. Lit dots fade between values over 220ms.
- **Accessibility:** `role="img"` with a spoken label (e.g. "Match clock 68:41"); the visual scoreline is hidden and a screen-reader heading carries full club names.

### OUT/IN substitution board (signature; the correction pattern)
The fourth official's board, repurposed: what went out (red) and what replaced it (green), side by side in two recessed panel-0 panels with OUT and IN labels, 4px LED dots. Used wherever a correction is summarised. Its caption gives the reason, the impact sentence ("Corrected 17 published items across 3 partners and 3 languages in 6.4 s") and the received/event times in tabular figures.

**The One Moment Rule.** This is the single authored motion moment: the IN panel's lit dots light up 260ms after OUT, over 420ms ease-out, like the board being raised. No other element animates for effect. The Corrections Center applies the same beat to each item board's IN panel, staggered board after board (260, 380, 500, then 620ms for the fourth and later), and, on Replay, to the impact fan's item nodes and their edges; it is the only motion on that screen, and under reduced motion none of it runs.

The two panels shrink to fit a narrow rail (`repeat(2, minmax(0, 1fr))`, `min-width: 0`, and the readout SVG at `max-width: 100%; height: auto`), so a long OUT or IN text scales down rather than overflowing. On Match Live the rail ("Corrections") lists every correction, newest first (empty, a 13px ink-2 sentence says what will appear there); each caption gives the summary (14px ink-1), "N published items corrected." (or "No published item rested on it.") in ink-2, and "Issued hh:mm:ss UTC" in tabular figures. When a corrected item is on the page the summary is a link to it (underline in hairline-strong, `currentColor` on hover), and the item it reaches is outlined (see Wire item, `:target`). In brief form (`brief`, for a page that states the summary and times itself, as the Corrections incident does) the caption keeps only the impact line.

### Verdict line
One sentence under the screen title, at 16px weight 500, led by a 12px round lamp in green, amber or red ("All 3 matches under control. 3 items await approval."). It is a `role="status"` region. Every screen leads with one. On Match Live it reads the run: amber "No replay is running. Start the matchday to watch it unfold." before a start; green "Live. N verified insights so far, M being verified." while running; green "Full time. …" with how many corrections reached their items; red when the replay stopped or the match service is unavailable. On Approvals it names how many items wait and since which match minute; on Corrections, how many corrections and what they reached (see Layout).

### Match keys (Match Live)
One square-cut key per match in a `nav` labelled "Matches": 36px tall, 12px side padding, panel-2 face with strong hairline edge and the key bevel, 13px weight 500 ink-2, club codes ("ARD v KES") in tabular figures with full names for screen readers. Hover and current (`aria-current="page"`) go panel-3 and ink-1; current drops the bevel, like a pressed key. A running match adds a 6px red lamp and "LIVE" as an 11px uppercase label in ink-1; a finished one a quiet "FT" in ink-3; otherwise nothing.

### Start key (Match Live)
The primary key with a 14px Lucide Play icon; it starts the replay of the whole matchday. Its label is its state:
- **Start matchday:** enabled.
- **Starting…:** while the request is in flight (spinner, `aria-busy`, no icon).
- **Matchday running:** disabled while any match runs.
- **Ready in m:ss:** disabled during the cooldown, counting down each second.
- **Daily limit:** disabled, with the API's reason as a note beside it ("… Ready again at hh:mm UTC.").

Notes are a `role="status"` line of 13px ink-1 text led by an 8px round lamp: amber for a refusal that will clear (409, daily limit), red when the service failed. A note lapses when the running state changes.

### Live scoreboard (Match Live)
A panel-1 board padded 32px (16px below 768): the 6px-dot LED scoreline ("ARD 2-1 KES") in a recessed panel-0 field, club names in 14px ink-2 under their codes, then the clock row: 3px-dot LED clock (00:00 before kick-off), broadcast minute (16px, 600, tabular, `min-width: 4ch`) and the run state as an 11px uppercase label with a 10px lamp: "Not started" (unlit), "Live" (the lit red tally lamp with its specular highlight, label ink-1), "Full time" (unlit), "Stopped" (amber lamp). A screen-reader heading speaks "Home 2, Away 1, 61'".

### Wire (Match Live)
"Minute by minute": a panel-1 panel padded 24px by 32px holding a `role="log"` (`aria-live="polite"`, additions only) of moments, newest first, divided by hairlines.
- **Loading:** three skeleton rows of panel-2 bars (14px and 40px), hidden from screen readers, while the stream connects and nothing has arrived.
- **Empty:** a 64ch ink-2 sentence; before the matchday starts it invites a start and lists what will appear, once running it says the first verified moment will appear here.
- **Reconnecting:** a `role="status"` line in amber above the list: "Connection lost. Reconnecting; nothing will be missed."

### Wire item (Match Live)
A two-column row (`7.5rem | 1fr`, `--space-4` gap, `--space-5` vertical padding; one column below 768).
- **When:** the broadcast minute (20px, 600, tabular) over the moment kind as an 11px uppercase ink-2 label with a 14px Lucide icon. Kinds are marked by icon, never colour: Goal (CircleDot), Big chance (Crosshair), Red card (RectangleVertical), VAR (Undo2), Press eases (TrendingDown), Press rises (TrendingUp), Momentum and Tactics (Waves).
- **Body, in order:** headline (16px, 600, -0.01em, an `h3` whose id is `moment-<id>`); the correction strap, if any; "As published" label, if amended; the claims (a 72ch list in ink-1); the meta row.
- **Meta row:** the Published status lamp, the AI tag only when a model wrote the insight (not for the deterministic template), and the provenance disclosure.
- **Provenance:** a `details` whose summary is a 14px Lucide ChevronRight (rotates 90deg open over `--duration-light`) and one line: "Verified on attempt N · model … · prompt …", or "Deterministic template, no model" / "… after N model attempts". Open, it lists every attempt in a recessed panel-0 block (`1.5rem | 4.5rem | 1fr`): number, model or "template", and the outcome ("passed every check" in ink-1; refusals and errors in ink-2).
- **Targeted:** reached from a rail correction (`.wire-item:has(.wire-item__headline:target)`), the item gets a 1px hairline-strong outline offset `--space-2` with the key radius; the headline scrolls in with `--space-6` margin.

States (from `itemState`):
- **Drafting:** no insight yet. Headline "Goal detected" and a meta line "Explaining and verifying" with a spinning 14px LoaderCircle (900ms linear). No lamp, no tag.
- **Published:** the Published status lamp (green, CircleCheck) in the meta row. The only state that shows a lamp: on corrected items the strap already names the state.
- **Retracted** (`EVENT_VOIDED`): headline and claims drop to ink-2 and are struck through with a 1px led-red line; the strap is labelled "Retracted" in red.
- **Amended** (`EVENT_AMENDED`): the strap is labelled "Corrected" in violet; an "As published" 11px uppercase ink-2 label introduces the original claims, struck through with a 1px led-violet line in ink-2.

### Correction strap
What changed, on the item it changed: under the headline, a recessed panel-0 strip with a strong hairline edge, 8px by 12px padding, 13px ink-1 summary led by an 11px uppercase label ("Retracted" red or "Corrected" violet).

### Brand mark
A 22x34 board held up: a 3x5 dot grid in a 2px-radius frame, top row red (out), bottom row green (in), the rest unlit.

### Data table
13px, left-aligned headers in ink-2 weight 500 over a strong hairline, 8px by 12px cells on hairline rows, panel-2 row hover, right-aligned tabular numerics, uppercase label caption.

### Partner keys (Broadcast Preview)
A vision mixer's bus: one key per partner in a group labelled "Partner on the monitor", numbered 1 to 3. 40px tall (44px on phones), panel-2 face, strong hairline edge, key bevel, 13px weight 500 ink-2. Contents, in order: a 24px cap (panel-0, Geist Mono, ink-3), the partner name, its language as an 11px uppercase label in ink-3, and an 8px tally lamp, lit red when that partner has a graphic on air (announced ", on air"), unlit (led-off) otherwise. The current key is `aria-pressed`: panel-3, ink-3 edge, ink-1, no bevel, and its cap lights white with panel-0 text.

### Key cap
The visible shortcut on a small key (`.key-cap`): 18px tall, 18px minimum width, 4px side padding, panel-0 face, strong hairline edge, 2px radius, Geist Mono 10px in ink-3, hidden from screen readers (the key carries `aria-keyshortcuts`). Every shortcut has one.

### Program monitor (Broadcast Preview)
One partner's broadcast as its viewers would see it, in a panel-1 housing with a hairline edge.
- **Bar:** the mode as an 11px uppercase label led by a 10px tally ("Program", lit red with the specular highlight when a lower third or strap is on air; "Preview" when a rundown row is chosen, never lit); the partner name (13px ink-1) with "Language · locale" in 11px ink-3; the 2px-dot LED match clock (00:00 before kick-off) at the right.
- **Stage:** a 16:9 frame in a panel-0 surround padded 12px, authored at 1920 by 1080; `--u: calc(100cqw / 1920)` is one authored pixel at the shown width, so every graphic scales with the frame. The feed is a placeholder pitch (faint 18% white lines on dark green); there is no video. The stage is `role="img"`; the rundown is its text equivalent.
- **Stage label:** the stage's spoken label defaults to the rundown pointer; a screen may pass its own (`stageLabel`), as the Approvals desk does to say the words are on the desk as text.
- **Held:** in preview, a lower third pending approval carries an amber "Pending approval · held off air" label at the top centre.
- **Safe areas** (G): action safe at 90% (dashed, 45% white) and title safe at 80% (dotted, 35% white). They differ by dash pattern, not hue: colour is reserved for state. Graphics sit inside title safe.

### Broadcast graphics (inside the monitor)
Set in Barlow Condensed in each partner's look.
- **Lower third:** a headline bar (46u, 700, the partner's accent) over a line panel (36u, 500). The headline carries the disclosure badge with the policy's exact label (none when the policy shows none), set in Geist, never restyled.
- **Correction strap:** a full-width strap (40u, 600) whose lead before the colon is bold. It preempts the lower third: while a strap is up, no lower third shows.
- **Score bug:** top left inside title safe; home, score (accent), away, clock. In program the clock runs on the match clock; in preview it shows the time the score changed.
- **Motion:** each graphic animates in over at most 360ms ease-out (fade and a 24u rise); none under reduced motion.

### Rundown (Broadcast Preview)
The monitor's accessible equivalent: a table, one row per moment and correction, newest first; headed "Rundown". Empty, a dashed panel says what will appear.
- **Columns:** time (broadcast minute, tabular, 4.5rem); moment (kind icon and label as an 11px uppercase ink-3 label; kinds are icons, not colour; corrections use RefreshCcw and add their title in ink-1, and only corrections carry a title); then one column per partner, headed by code, that never moves. The current partner's column header is ink-1 and its cells carry a faint 2.5% white wash.
- **Cells:** each partner cell is a button that puts that partner on the monitor and previews that row; the moment cell previews the row for the current partner (`aria-pressed`). A cell shows the shared status lamp, the AI tag when the version carries a disclosure, and the partner's words in ink-2 in its own `lang`; "Not sent" in ink-3 when that partner has no version.
- **States** (the shared lamp, read at the match clock): Queued (not yet due), On air, Published (aired), Pending approval (held), Dropped (rejected).
- **Selected row:** panel-2 with a 2px board-white inset rule on the left.

### Ticket (Approvals)
One call-sheet entry: a full-width button on panel-1 with a hairline edge, 8px by 12px padding, 2px radius. A head line of 11px uppercase labels: the partner code in ink-1, the moment kind (12px Lucide icon and label) in ink-3, and at the right the match minute it has waited since in amber, tabular (waiting is a state, so the time carries the amber); beneath, the partner's words in 13px ink-2 in their own `lang`. Hover goes panel-2. The current ticket (`aria-current="true"`) is panel-2 with a strong hairline edge, a 2px board-white inset rule on the left and ink-1 text.

### Reject form (Approvals)
Opened by R on the desk: a panel-1 panel padded 16px with a strong hairline edge. The label "Reason for rejecting" (11px uppercase, ink-2); a full-width 36px input on panel-0 with the focus ring, focused on open, limited to one line without links; an error, when the reason fails, as `role="alert"` ink-1 text led by an 8px red lamp (the input `aria-invalid` and described by it); then the keys: "Send rejection" (danger key) and "Esc Cancel" (default key, `aria-keyshortcuts="Escape"`). Esc in the input cancels too.

### Decisions log (Approvals)
The audit trail beneath the floor, headed "Decisions", newest first; empty, "No decisions yet this match." in ink-3. A data table: decided (studio time, `Europe/London`, hh:mm, matching the top-bar clock), partner, the item's headline in its own `lang`, the decision as text ("Approved" or "Rejected", never colour alone), "Now" with the shared status lamp read at the match clock (Queued, On air, Published, Pending approval, Dropped), the editor followed by " · duty editor (demo identity)" in ink-3, and the reason. On phones each row becomes a card of labelled lines (`6rem | 1fr`, labels from `data-label` in 11px uppercase ink-3, empty cells hidden); the table keeps explicit roles (`table`, `rowgroup`, `row`, `cell`) so its semantics survive the restyle.

### Impact fan (Corrections)
The correction, the insights resting on it and every partner item it reached, drawn as one fan in an SVG (`role="img"`, labelled "summary: reached N insights and M partner items"; the item boards are its text equivalent). A recessed panel-0 field with a hairline edge and the key radius, full width; on phones a stacked layout replaces it (see Corrections, Phones). Three columns of 28-unit nodes (panel-2 fill, strong-hairline edge, 2px radius, 14px ink-1 Geist), joined by 2px strong-hairline edges:
- **Event node** (left, vertically centred): the board's own text, `OUT → IN` ("2-1 → 1-1"), with a board-white edge.
- **Insight nodes** (centre): named by moment kind and broadcast minute ("Goal 67'"), or "Insight" when the moment is not on the feed.
- **Item nodes** (right): "Partner · locale" ("Tribuna Austral · es-MX"), each joined to the insight it rests on.
- **Colour:** item nodes and their edges take their state colour only: retracted red, amended violet, escalated amber. Everything else is neutral.
- **Titles:** each node's `<title>` carries its id (the event node's carries the summary), for a hover read without cluttering the fan.

### Item board (Corrections)
One partner item a correction reached, as a list item: a panel-1 panel padded 16px with a hairline edge.
- **Head:** the partner name as an `h3` (14px, 600, ink-1), its language as an 11px uppercase ink-3 label, the shared status lamp (Retracted, Amended, or Pending approval for an escalation), and, when the item had been held, "was held for an editor" in the same label style.
- **Panels:** OUT and IN side by side (`repeat(2, minmax(0, 1fr))`, stacked on phones), each a recessed panel-0 panel padded 12px with a red OUT or green IN label (hidden from screen readers; each panel is a group labelled "Out: Partner" / "In: Partner").
- **OUT:** the published headline (600, ink-1) and first claim (13px ink-2) in the item's own `lang`, struck with a 1.5px line, red when the item was pulled and violet when it was amended, followed by a visually hidden "(withdrawn)" or "(replaced)".
- **IN:** the new version's words, unstruck; or, in 13px ink-2, "Pulled off air", "Withdrawn before air" (the item was held), or "Held for an editor: pending approval" (escalated, beneath the held version). Words missing from the feed say so ("Its words are not on the feed.", "The new version is not on the feed yet").
- **Motion:** the IN panel lights a beat after OUT, staggered across boards (see The One Moment Rule).

### Replay (Corrections)
A small default key beside "What it reached". It re-runs the One Moment light-up across the item boards (260, 380, 500, 620ms) and the fan's item nodes and their edges, then moves focus to the first board's heading (`#first-change`, `tabindex="-1"`). Under reduced motion nothing animates, but focus still moves, so the replay is felt.

### Seal (Provenance, Verify)
The record's answer, first in the record above a hairline: a 36px Lucide shield (stroke 1.5) beside a 20px weight-600 title, then the signer line in 13px ink-2 ("key · Issued by …, signed at hh:mm:ss UTC"). Three tones, from `sealOf`:
- **Verified** (green ShieldCheck): "Signed and unchanged". Only the studio's production key (ES256) earns it.
- **Development** (amber ShieldAlert, detail in amber): "Unchanged, signed with a development key"; a local key proves nothing outside the studio.
- **Failed** (red ShieldX): "Does not verify", with the reason beneath in red, weight 500.
- **On paper:** set larger than the page title (24px title, 44px icon).

### Annotated record (Provenance, Verify)
The item itself, annotated: a panel-1 panel padded 32px (16px on phones) with a hairline edge, `id="record"`, `tabindex="-1"`.
- **Head** (13px ink-2): the partner name (600, ink-1), its locale in the data font (12px ink-3, BCP 47 casing kept, not a label), "Version N, as signed" in ink-3, the shared status lamp (a rejected item reads Dropped), and the disclosure exactly as the partner's policy labelled it, in the AI tag's style (18px, blue edge at 60%, in the item's `lang`).
- **Headline:** `clamp(1.75rem, 1.25rem + 1.5vw, 2.5rem)`, 600, 1.15, -0.02em, 30ch, balanced, in the item's own `lang`.
- **Claims:** an ordered list, each above a hairline: the claim at 18px/1.5 ink-1 (60ch) and, from 768 in a 16rem column beside it, a margin note (13px ink-2, strong-hairline left rule): "Rests on events E1, E2 and stats S1", ids in the data font (Geist Mono, 12px).
- **Below:** Life and Facts under a hairline, side by side from 1280.

### Life
"Its life": the item's steps as a lamp on one strong hairline, from `lifeOf` (Written, Remade, Checked, Localised, Approved or Rejected, then the ending), each a 14px weight-600 label over a 13px ink-2 detail. Process steps are hollow 12px lamps (ink-3 edge). The ending is lit in its State Vocabulary colour: On air red, Held amber, Pulled red, Replaced violet; Kept off air (and a Rejected step) lit ink-3. Never colour alone: every lamp has its label.

### Facts
"The record": a `dl` of 11px uppercase ink-3 terms over 13px ink-1 values: Item, Match and feed entry, Key, Content hash (SHA-256), Signature (algorithm). Ids, hash and signature are set in the data font at 12px and break anywhere.

### Picker (Provenance)
"Items on record · N": a call sheet on panel-1 with a hairline edge, its heading sticky inside it. Rows are links (`code | headline | minute + compact lamp`, `2.75rem | 1fr | auto`, 12px by 16px padding, hairline-divided): partner code as an 11px label in ink-3, the headline truncated in 13px ink-2, the minute and the compact status lamp in ink-3. Hover panel-2; the current row (`aria-current="page"`) is panel-3 with ink-1 text and code. The list scrolls, so its focus ring is drawn inset (`inset 0 0 0 2px led-white, inset 0 0 0 4px panel-0`) where the scroller cannot clip it.

### The call (Proving Ground)
The gate's verdict lit on the board: a panel-1 panel padded 24px with a hairline edge. "The call" panel heading; an LED readout reading NO-GO (red) or GO (green) at 6px dots, filling the panel's width on a panel-0 field padded 16px (`role="img"`, "The call: no-go"); the subject in 16px 600 ink-1, balanced ("Analyst prompt v1.4 against production's v1.2"); above a hairline, a facts `dl` of 11px uppercase ink-3 terms over 14px ink-1 values: Benchmark ("20 matches from …", tabular), Models (joined ", then "), Recorded (the date, in `<time>`).

### Poll station (Proving Ground)
"The poll · 7 rules": an ordered list on panel-1 with a hairline edge, one station per rule in the gate's order, hairline-divided, padded 12px by 24px. Columns `6rem | minmax(0, 24rem) | minmax(7rem, auto)`, packed to the start so the figure sits beside its label rather than across the panel. The call: a 10px round lamp (green go, red no-go) with "Go" or "No-go" in 14px 600 ink-1, never colour alone. The title: 16px 600 ink-1. The candidate's figure: 20px 600 tabular, right-aligned, ink-1, lit red only when that station is no-go (the White Clock Rule's breach exception). Beneath the title, production's figure ("Production …", ink-2) and the allowance ("Rule: may drop 3 points", ink-3), 14px.

**Measure naming.** One label per measure, identical in the poll, the table and the benchmark (from `RULE_TEXT`): Unsupported claims on air (rule: none), Policy breaches (none), Planted lies refused (every one), Corrections carried (every one), Planted stories found (may drop 3 points), Written by the model (may drop 5 points), Time to explain (p50) (may grow 15% and 2 s). Reported only: About a real moment, Passed first time, Time to explain (p95), Cost of the run.

### Side by side (Proving Ground)
The data table, Measure | Production | Candidate: the gated measures in the poll's order (rates also as counts, "hit of N (rate%)"), then the reported ones with "(reported)" in ink-3 after the label. No colour in the table; the poll carries the state.

### Unsupported claim (Proving Ground)
Each failure from either run, candidate first: a panel-1 item padded 16px with a hairline edge. A 14px ink-3 line "Candidate · match id · item id" (ids in the data font, 12px, breaking anywhere); the claim's text in ink-1, rendered as text, never markup; its reasons as a 14px ink-2 bulleted list; "Rests on E1, E2" in ink-3. None: a 65ch ink-2 sentence, "No claim on air at full time was unsupported, in either run."

### Benchmark panel (Proving Ground)
"The full benchmark": a panel-1 panel padded 24px. A 65ch ink-2 lede ("The harness's own reference run: N matches from …, explained by the template with no model and no cost.") over a facts `dl` in auto-fit `minmax(12rem, 1fr)` columns: 11px uppercase ink-3 terms over 16px 600 ink-1 tabular values, using the measure names above.

## Do's and Don'ts

### Do:
- **Do** use one colour, one icon and one label per item state, exactly as in the State Vocabulary table.
- **Do** keep clocks and scorelines lit white; set numbers in tabular figures.
- **Do** draw LED readouts with 5x7 glyphs, a 1-dot gap, whole-pixel dot sizes, fixed character width and faint unlit dots.
- **Do** give the featured match the largest board on the wall.
- **Do** summarise every correction with the OUT/IN board.
- **Do** lead every screen with a verdict line.
- **Do** use the 2px key radius for hardware and perfect circles for lamps.
- **Do** show the focus ring (2px gallery-black gap, 2px board-white ring) on every focusable element.
- **Do** honour `prefers-reduced-motion`: all animation and transition durations collapse to 0.01ms (Match Live also stops the verifying spinner and the provenance chevron's rotation outright).
- **Do** keep what went out visible: strike retracted text in red, and keep amended claims struck in violet under "As published".
- **Do** let a key's label carry its state (Starting…, Matchday running, Ready in m:ss) rather than hiding why it is disabled.
- **Do** label replay mode, synthetic data and AI content.
- **Do** give every keyboard shortcut a visible key cap and `aria-keyshortcuts`.
- **Do** keep a text equivalent beside every picture of a broadcast: the rundown lists everything the monitor shows.
- **Do** name the duty editor as a demo identity wherever a decision names an editor; this demo has no sign-in.
- **Do** keep an editor's keys waiting until the item on the desk has been seen: never let a decision land on an item the editor has not had time to read.
- **Do** show a correction's reach as substitutions: every partner item it reached OUT and IN, with a text equivalent beside any picture of it.
- **Do** give each measure one name across the poll, the table and the benchmark, and say in the verdict which rules said no and by how much.

### Don't:
- **Don't** add glow, bloom or drop shadows, and don't use gradients (the tally lamp highlight is the only exception).
- **Don't** build rounded-card soup: no radius above 2px on containers, no floating cards.
- **Don't** use green, amber, red or violet for anything that is not a state; don't use blue for anything but the AI tag.
- **Don't** colour a clock or scoreline by state.
- **Don't** convey state by colour alone.
- **Don't** add motion beyond the OUT/IN light-up (including its staggered repeat on the Corrections item boards and fan) and state transitions of 160 to 220ms (the functional exceptions are loading spinners, the disclosure chevron, and broadcast graphics animating in within 360ms inside the monitor, as they do on air).
- **Don't** mark moment kinds with colour; a kind is an icon and a label.
- **Don't** repeat a correction's state with a lamp when its strap already names it.
- **Don't** use partner or tenant brand colours or the graphics face in the chrome; they belong only inside the Broadcast Preview monitor's stage.
- **Don't** set Paper in the control room, and don't give the development key's seal green: only ES256 is "Signed and unchanged".
- **Don't** light a passing gate figure green or colour the side-by-side table; only a breached figure and the lamps carry state.

### Open items
- Nothing on air links to Verify yet: no QR code or short link on the partner graphics or in the Broadcast Preview monitor, so a viewer can only reach `/verify/[itemId]` from a shared URL.
- The Proving Ground shows the recorded runs in `eval/results` (production-20, candidate-20, template), not the latest CI run; a pull request's own verdict is not yet linked from the screen.
- Paper has no print stylesheet; the Verify page prints with its masthead and links as on screen.
