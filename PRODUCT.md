# Product

<!-- impeccable:product-schema 1 -->

> Recorded from the project plan (Oct 7, 2026) without a live interview, at the owner's instruction to proceed unattended. Items marked *(inferred)* are reasonable readings of the plan, not confirmed answers.

## Platform

web

## Users

- **Head of matchday production** at the league's in-house studio (persona: Hannah Okafor, Meridian League Studios). Runs up to ten live matches at once and is accountable for nothing embarrassing going on air for any partner. Works in a dark production gallery, glancing at the screen between other monitors.
- **Partner producer** at a broadcast partner (persona: Tomás Ibarra, Tribuna Austral). Approves narrative items for his network, in Spanish, often from Microsoft Teams.
- **Editorial compliance lead** at an EU partner (persona: Lena Vogt, Rheinblick Sport). Needs every AI item disclosed or signed off by a named editor, with an audit trail.
- **Platform engineer** at the studio (persona: Sam Reyes). Ships prompt and model changes safely and keeps latency and cost within budget.
- **Evaluators:** hackathon judges (Microsoft and Premier League staff) who often decide from a two-minute video, screenshots and a three-minute guided tour. *(inferred: they are a primary audience for every screen's first impression)*
- **Fans** (Meridian+ app) are indirect users: a casual and a data-hungry fan see the same verified insight in different forms.

## Product Purpose

Fourth Official is the enterprise control layer that lets a league studio put AI-generated match intelligence on air safely, for many broadcast partners, in many markets and languages. One verified pipeline (ingest, interpret, explain, render, personalise) feeds every partner under its own editorial policy. Success means: zero unsupported claims published, every correction propagated to all partners within seconds, and cost per match visible to the cent.

## Positioning

Other AI match-insight tools show one viewer on a happy path. Fourth Official is built for the studio operating model: verify once, render many ways; each partner sets its own policy; sensitive items route to human approval; every published item carries signed provenance; when source data changes (a goal disallowed, a scorer reassigned), it finds and corrects everything already published, everywhere; and no prompt or model change ships without passing a measured release gate.

## Operating Context

- A matchday control room: several matches live, items flowing per minute, approvals with SLA timers, corrections arriving from VAR and the accreditation panel.
- Broadcast conventions the users grew up with: program monitor, timecode, lower thirds, tally lights, rundowns, safe-title areas.
- Partners approve in Microsoft Teams (Adaptive Cards) or an in-app queue.
- Screens: Control Room, Match Live (2D pitch), Broadcast Preview, Approvals, Corrections Center, Provenance and public Verify page, Policy Studio, Proving Ground / Release Gate, Operations, optional Fan View (mobile).
- Designed for 1920×1080 and 1440×900 control-room displays, minimum 1280 wide; Fan View is mobile-first.

## Capabilities and Constraints

- Numbers are computed in code, never by a language model; words come from models; facts are checked twice (canonical, then after localisation).
- Languages: English (en-GB), Spanish (es-MX), German (de-DE). German runs about 30% longer; layouts must hold.
- Item states: on air, published, pending approval, retracted, amended, dropped. Each state needs one consistent colour, icon and text label.
- Replay mode, AI-generated content and estimates are always labelled.
- All data is synthetic. The league, clubs, players, broadcasters and app are fictional: Meridian League, eight clubs (Harbour City, Northgate FC, Kingsbridge Athletic, Ashford Vale, Calder Town, Westmere, Brackley Mills, Saltmarsh), partners Northlight Sport (en-GB), Tribuna Austral (es-MX), Rheinblick Sport (de-DE), app Meridian+, studio Meridian League Studios.
- Never use real league, club, player or broadcaster names, logos or colours; no purple league palette, no lion.
- Tenant brand colours appear only inside each partner's Broadcast Preview; the application chrome stays neutral.
- Undecided: final product name check, and the Saguaro Cloud brand colour (placeholder only).

## Brand Commitments

- Product name: Fourth Official, by Saguaro Cloud. The name comes from football's fourth official: oversight of the touchline and the rules, not play.
- Voice: plain English, sentence case, calm and precise; jargon only with a tooltip. *(inferred from the plan's copy rules)*
- Microsoft products are named factually in text; no Microsoft logos unless brand guidelines permit.

## Evidence on Hand

- No real customers, testimonials, benchmarks or footage exist. Results numbers (unsupported-claim rate, recall, latency, cost per match) will come from the Proving Ground's simulated matches and must not be invented before then.
- No Saguaro Cloud logo or brand colour has been supplied yet.

## Product Principles

1. Brand safety first: nothing reaches air without verification, policy and, where required, a named human.
2. One truth, visibly traced: every number and sentence is one click from its evidence.
3. State is always legible: anyone glancing at a screen can tell what is live, pending, corrected or broken.
4. Honest by default: synthetic data, replay mode, AI content and estimates are labelled.
5. Executive-readable in five seconds: every screen leads with its headline number or state.

## Accessibility & Inclusion

- WCAG 2.2 AA contrast, including state colours on dark surfaces; state is never conveyed by colour alone.
- Full keyboard operation (approvals use A, R and E shortcuts), visible focus rings, `aria-live` regions for new items.
- Respect `prefers-reduced-motion`; no layout shift as live data arrives.
