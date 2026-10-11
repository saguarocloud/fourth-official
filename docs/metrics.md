# Metrics

The stats engine (`services/stats-engine`, stage two, Interpret) computes every number in the product. **No language model computes a number.** Each metric is a pure function over match events that returns its value **and the exact event IDs it used**. A `MetricSnapshot` contract (`packages/contracts`) freezes one metric, for one scope (a club or the whole match), over one window (`5m`, `15m`, `match`), at one moment (`asOf`, `asOfSeq`). Claims built on a snapshot cite it, so every sentence on air traces back to events.

Snapshot IDs are deterministic: `ms-<match>-<metric>-<scope>-<window>-s<asOfSeq>-v<version>`. The contract checks that the ID names exactly the snapshot's fields. It also checks that the metric and scope agree (`control_chaos` is match-wide, everything else is per club), that the evidence lists each event once in match order, and that a restatement supersedes the same snapshot at the previous version. Values are rounded to 4 decimals and never published as `-0.0`. A metric that cannot be defined (PPDA with no defensive actions, chaos in an empty window) has value `null`, never a made-up number.

## Input

Everything goes through `prepare(context, events)`, which:
- refuses events from another match or by a club not in it;
- refuses two different events with the same sequence number;
- refuses matches of more than 5,000 events (real matches have about 2,500 to 3,000);
- keeps only the latest version of a corrected event;
- sorts by sequence and indexes by `seq`.

Snapshots for one moment cut each window once and share it across all metrics.

## Windows

A window holds the events up to and including the moment (by `seq`) whose match time falls inside it: `(t - 5 min, t]`, `(t - 15 min, t]`, or the whole match so far. Match time is **monotone**: second-half time continues from the end of the first half, added time included. A first-half added-time event at 47:00 therefore sits before a second-half event whose clock reads 46:00. Per-minute rates use the window's length, capped at the time elapsed, with a minimum of one minute.

## Direction of play

The home side attacks the goal at x = 105 m in the first half and teams switch ends at half time. "Final third", "own 60%" and xG geometry are always computed from the acting team's point of view (`MatchContext.progress`).

## Definitions

| Metric | Scope | Definition | Evidence |
|---|---|---|---|
| `passes` | club | Passes attempted by the club | The club's passes |
| `pass_completion` | club | Completed ÷ attempted (null without passes) | The club's passes |
| `possession` | club | The club's share of all passes (the standard event-data proxy) | All passes |
| `field_tilt` | club | The club's share of final-third passes (origin at 2/3 of the way up the pitch or beyond) | All final-third passes |
| `shots` | club | Shots taken | The club's shots |
| `shots_on_target` | club | Shots that scored or were saved | The club's shots |
| `xg` | club | Sum of the xG model over the club's shots | The club's shots |
| `momentum` | club | The club's xG minus the opponent's xG in the window | All shots |
| `ppda` | club (pressing) | Opponent passes in its own 60% of the pitch ÷ the pressing club's tackles, interceptions and fouls in that area (null without actions). Lower is a more aggressive press | Those passes and actions |
| `pressing_intensity` | club | Pressure events applied per opponent pass or carry (undefined if the opponent had no touches). Normalised by the opponent's touches, so a side that keeps the ball doesn't make its opponent's press look busier | The club's pressure events and the opponent's passes and carries |
| `control_chaos` | match | 0–100, defined below | Turnovers, passes and located events |

### Expected goals (xG)

Logistic regression, independent of the simulator's own model (the pipeline measures shots; it does not peek at how they were generated):

`logit = -1.0 - 0.105 × distance_m + 2.0 × angle_rad - 0.85 × header - 1.1 × pressure`

Here distance is measured to the centre of the goal being attacked; angle is the angle subtended by the 7.32 m goal mouth; header is 1 for headed shots; pressure (0–1) is recorded on the shot. A central shot from 11 m is worth 0.2952. **Penalties** (a shot straight after a penalty was awarded to the same team) are worth 0.76, the typical conversion rate, not their open-play geometry. The award decides the value, so it is listed in the evidence straight before its shot, and snapshots use the awards known over the whole match: a window that starts between an award and a delayed kick still values the kick as a penalty.

### Pass difficulty (0–100)

`100 × (0.45 × min(distance / 50 m, 1) + 0.35 × pressure + 0.2 × kind)`

Pressure is the intensity of a pressure event on the passer immediately before the pass (the previous sequence number, as the feed records a press right before the action it affects), or 0. The kind factors are: ground 0.2, lofted 0.5, switch 0.6, cross 0.7, through 0.8. Ratings are per pass (one decimal) and are not published as snapshots.

### Control versus chaos (0–100)

`100 × (0.4 × T + 0.4 × C + 0.2 × E)` where:
- **T** = min(turnovers per minute ÷ 4, 1);
- **C** = 1 − min(mean passes per possession chain ÷ 8, 1), where chains = turnovers + 1;
- **E** = Shannon entropy of event locations over a 6 × 4 grid, divided by ln 24.

Frequent turnovers, short chains and scattered play push it up; long controlled possessions bring it down. A window with neither passes nor turnovers has no value. With fewer than 24 located events the entropy term cannot reach its maximum, so very sparse windows read slightly calmer than they are.

## Not yet covered

Speed, distance covered, sprints and player speed badges need tracking frames and arrive with them. Correction-driven restatement (recompute affected snapshots as new versions that supersede the old) is the next stats PR.
