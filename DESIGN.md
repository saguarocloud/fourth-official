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
- Geist for UI text with tabular figures; Geist Mono only on key caps.

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

**The One Blue Rule.** Blue is reserved for the AI tag. Nothing else is blue.

**The White Clock Rule.** Clocks and scorelines are lit white. A number becomes a state colour only when it is itself a state (a pending count, an SLO breach).

## Typography

**Display font:** none; the LED readout takes the display role.
**Body font:** Geist (with system-ui, sans-serif)
**Label/mono font:** Geist Mono (with ui-monospace), only for key-cap shortcuts.

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

The shell is a three-column grid: top bar across, nav rail left, main wall centre, live rail right (`232px | 1fr | 360px`). The top bar holds identity (mark, product, studio, replay label), hairline-separated readouts (event-to-air p95 vs SLO, pending approvals, corrections, cost so far) and the LED studio clock at the far right.

The main wall leads with the page header and verdict, then the match wall: a two-column grid with 16px gaps where the featured match spans both columns and carries the largest board; other boards sit two across below. The live rail holds the latest correction as an OUT/IN board above the activity log.

Spacing runs on a 4px base (4, 8, 12, 16, 24, 32). Main padding is 24px by 32px; boards pad 24px (featured 32px); rail sections are separated by 32px.

Breakpoints:
- **1440 and up:** `232 | 1fr | 360`.
- **1280 to 1439:** `208 | 1fr | 320`; readout padding tightens to 12px.
- **1024 to 1279:** nav collapses to a 64px icon rail (labels kept for screen readers), `64 | 1fr | 300`; the featured board stacks to a single column.
- **Below 1024:** everything stacks (top, nav as a horizontal icon strip with 40x44 targets, main, rail); top-bar readouts become a two-column grid; main padding 16px.
- **Below 768:** the match wall goes to one column; stats go two across.

No layout shift as live data arrives: fixed-width LED glyphs and tabular figures hold every width.

## Elevation & Depth

Flat. There are no drop shadows and no glow. Depth comes from tonal layering of the panel blacks (panel-0 page and LED field, panel-1 panels, panel-2/3 keys) and 1px hairlines. Readouts sit in a recessed panel-0 field inside a panel-1 board, like the physical LED panel set into its housing.

### Shadow Vocabulary
- **Key bevel** (`box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.05)`): a 1px top highlight on default keys; removed on press.
- **Focus ring** (`box-shadow: 0 0 0 2px #07090b, 0 0 0 4px #f2f5f7`): the only outer ring, on every focusable element.

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
- **Shortcut cap:** optional single-key cap in Geist Mono 11px with a 1px currentColor border (approvals use A, R, E); announced via `aria-keyshortcuts`.
- **Loading / Disabled:** spinner and `aria-busy`; disabled at 50% opacity.

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
The fourth official's dot matrix, drawn as SVG circles.
- **Glyphs:** 5x7, digits, A to Z and match marks (`: . , + - ' % / $`); unknown characters fall back to `?`.
- **Spacing:** 1-dot gap between dots and one blank column between characters; every character has the same width, so a ticking clock never changes size.
- **Dot size:** whole CSS pixels only (2 to 6) so dots stay on the pixel grid. Clocks use 3px; the OUT/IN board 4px; scorelines 6px.
- **Unlit dots:** always drawn faintly (led-off), so the readout keeps its shape when values change.
- **Scorelines scale fluidly:** the scoreline fills its field width (max 26rem on standard boards, 60rem on the featured board), so the featured match reads largest on the wall.
- **Tones:** white by default; green, red, amber, violet, blue available, used by the state rules above. Lit dots fade between values over 220ms.
- **Accessibility:** `role="img"` with a spoken label (e.g. "Match clock 68:41"); the visual scoreline is hidden and a screen-reader heading carries full club names.

### OUT/IN substitution board (signature; the correction pattern)
The fourth official's board, repurposed: what went out (red) and what replaced it (green), side by side in two recessed panel-0 panels with OUT and IN labels, 4px LED dots. Used wherever a correction is summarised. Its caption gives the reason, the impact sentence ("Corrected 17 published items across 3 partners and 3 languages in 6.4 s") and the received/event times in tabular figures.

**The One Moment Rule.** This is the single authored motion moment: the IN panel's lit dots light up 260ms after OUT, over 420ms ease-out, like the board being raised. No other element animates for effect.

### Verdict line
One sentence under the screen title, at 16px weight 500, led by a 12px round lamp in green, amber or red ("All 3 matches under control. 3 items await approval."). It is a `role="status"` region. Every screen leads with one.

### Brand mark
A 22x34 board held up: a 3x5 dot grid in a 2px-radius frame, top row red (out), bottom row green (in), the rest unlit.

### Data table
13px, left-aligned headers in ink-2 weight 500 over a strong hairline, 8px by 12px cells on hairline rows, panel-2 row hover, right-aligned tabular numerics, uppercase label caption.

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
- **Do** honour `prefers-reduced-motion`: all animation and transition durations collapse to 0.01ms.
- **Do** label replay mode, synthetic data and AI content.

### Don't:
- **Don't** add glow, bloom or drop shadows, and don't use gradients (the tally lamp highlight is the only exception).
- **Don't** build rounded-card soup: no radius above 2px on containers, no floating cards.
- **Don't** use green, amber, red or violet for anything that is not a state; don't use blue for anything but the AI tag.
- **Don't** colour a clock or scoreline by state.
- **Don't** convey state by colour alone.
- **Don't** add motion beyond the OUT/IN light-up and state transitions of 160 to 220ms.
- **Don't** use partner or tenant brand colours in the chrome; they belong only inside Broadcast Preview.

### Open items
- A condensed broadcast face for Broadcast Preview graphics (lower thirds, score bugs) has not been introduced; Geist is the only text face today.
- A light theme for Provenance and the public Verify page has not been built; the system is dark only (`color-scheme: dark`).
