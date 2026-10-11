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

**The White Clock Rule.** Clocks and scorelines are lit white. A number becomes a state colour only when it is itself a state (a pending count, an SLO breach).

### Partner looks (Broadcast Preview monitor only)
Each partner's graphics are drawn in its own look, inside the 16:9 stage and nowhere else. These colours are graphics, not signals.
- **Northlight Sport** (NLS, English, en-GB): navy panel #0E1A2B, aurora green accent #3DDC97 with navy ink on it; sentence case. Strap: green with navy ink.
- **Tribuna Austral** (TRA, Spanish, es-MX): panel #1C120C, orange accent #FF7A1A with #1C120C ink on it; the lower-third headline, strap lead and score bug set italic uppercase. Strap: orange with #1C120C ink.
- **Rheinblick Sport** (RHB, German, de-DE): stone panel #F1ECE3, ink #13232C; a 10-unit copper #B5552A rule on the headline and a copper score; formal weight (headline 600). Strap: copper with white ink.

**The Stage Rule.** Partner colours live inside the monitor's stage only, never in the chrome. Around the frame the board's palette and signal lights apply unchanged; inside it, no partner colour means state.

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

Spacing runs on a 4px base (4, 8, 12, 16, 24, 32). Main padding is 24px by 32px; boards pad 24px (featured 32px); rail sections are separated by 32px.

Breakpoints:
- **1440 and up:** `232 | 1fr | 360`.
- **1280 to 1439:** `208 | 1fr | 320`; readout padding tightens to 12px.
- **1024 to 1279:** nav collapses to a 64px icon rail (labels kept for screen readers), `64 | 1fr | 300`; the featured board stacks to a single column.
- **Below 1024:** everything stacks (top, nav as a horizontal icon strip with 40x44 targets, main, rail); top-bar readouts become a two-column grid; main padding 16px.
- **Below 768:** the match wall goes to one column; stats go two across.
- **Broadcast Preview only:** 1800 and up puts the rundown beside the monitor; 720 and below is the phone layout above.

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
- **Shortcuts:** every shortcut has a visible key cap and `aria-keyshortcuts`, shipped together with the handler, never one without the other. Broadcast Preview has 1/2/3, G and Esc; Approvals will add A, R and E the same way.
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

**The One Moment Rule.** This is the single authored motion moment: the IN panel's lit dots light up 260ms after OUT, over 420ms ease-out, like the board being raised. No other element animates for effect.

The two panels shrink to fit a narrow rail (`repeat(2, minmax(0, 1fr))`, `min-width: 0`, and the readout SVG at `max-width: 100%; height: auto`), so a long OUT or IN text scales down rather than overflowing. On Match Live the rail ("Corrections") lists every correction, newest first (empty, a 13px ink-2 sentence says what will appear there); each caption gives the summary (14px ink-1), "N published items corrected." (or "No published item rested on it.") in ink-2, and "Issued hh:mm:ss UTC" in tabular figures. When a corrected item is on the page the summary is a link to it (underline in hairline-strong, `currentColor` on hover), and the item it reaches is outlined (see Wire item, `:target`).

### Verdict line
One sentence under the screen title, at 16px weight 500, led by a 12px round lamp in green, amber or red ("All 3 matches under control. 3 items await approval."). It is a `role="status"` region. Every screen leads with one. On Match Live it reads the run: amber "No replay is running. Start the matchday to watch it unfold." before a start; green "Live. N verified insights so far, M being verified." while running; green "Full time. …" with how many corrections reached their items; red when the replay stopped or the match service is unavailable.

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

### Don't:
- **Don't** add glow, bloom or drop shadows, and don't use gradients (the tally lamp highlight is the only exception).
- **Don't** build rounded-card soup: no radius above 2px on containers, no floating cards.
- **Don't** use green, amber, red or violet for anything that is not a state; don't use blue for anything but the AI tag.
- **Don't** colour a clock or scoreline by state.
- **Don't** convey state by colour alone.
- **Don't** add motion beyond the OUT/IN light-up and state transitions of 160 to 220ms (the functional exceptions are loading spinners, the disclosure chevron, and broadcast graphics animating in within 360ms inside the monitor, as they do on air).
- **Don't** mark moment kinds with colour; a kind is an icon and a label.
- **Don't** repeat a correction's state with a lamp when its strap already names it.
- **Don't** use partner or tenant brand colours or the graphics face in the chrome; they belong only inside the Broadcast Preview monitor's stage.

### Open items
- A light theme for Provenance and the public Verify page has not been built; the system is dark only (`color-scheme: dark`).
