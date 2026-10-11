# Moments

The Moment Detector (`services/moments`) decides what in a match is worth explaining (stage three, Explain). It is deterministic: rules over events and metric snapshots, never a model. Each moment (`Moment`, `packages/contracts/schemas/moment.schema.json`) cites exactly the events and snapshots that show it, so the Analyst explains from the same evidence the Verifier later checks.

## Event moments

These are read off single events as they arrive.

| Kind | Rule | Club | Evidence |
|---|---|---|---|
| `goal` | A `GOAL` event | The credited side | The shot and the goal |
| `big_chance` | A shot that didn't go in, worth at least 0.35 xG (stats-engine model; a penalty is 0.76) | The shooting side | The shot (and the penalty award) |
| `red_card` | A red or second yellow card | The side that lost a player | The foul (if recorded) and the card |
| `var_overturn` | An overturned `VAR_DECISION` | The side whose event was overturned | The overturned event, the VAR checks and the decision |

## Shift moments

These come from a metric moving. They are checked once per minute of monotone match time (see `docs/metrics.md`) from the 20th minute, when a full baseline first exists.

| Kind | Rule |
|---|---|
| `pressing_collapse` | Over the last 5 minutes, `pressing_intensity` is at most 0.4× its value over the 15 minutes before that. The baseline must be at least 0.15 pressures per opponent touch: a press too light to matter can't collapse. |
| `pressing_surge` | The 5-minute value is at least 2.5× the baseline, and at least 0.15. |

- A shift must hold at three consecutive minute checks before it is reported.
- The same kind of shift for the same club then stays quiet for 15 minutes.
- The moment cites both snapshots and carries the `before` and `after` values. The Analyst therefore quotes numbers the stats engine computed, never its own arithmetic.

### Calibration

`pressing_intensity` counts pressures per opponent pass or carry. Pressures per minute proved too noisy, because a side that keeps the ball gives its opponent more chances to press. The rates below were measured on 30 ordinary simulated matches (seeds 7000–7029), where neither side's style changes, so every shift found is noise.

| Rule variant | Collapses per match | Surges per match |
|---|---|---|
| ×0.4, 2 checks, surge ×2.0 | 0.43 | 0.43 |
| ×0.4, 3 checks, surge ×2.5 (chosen) | 0.07 | 0.00 |
| ×0.4, 4 checks, surge ×2.5 | 0.00 | 0.00 |

Requiring three checks delays a real collapse by about a minute compared with two. The tests pin the false-alarm rate on ordinary matches.

## Incremental detection

`detect(match, state)` reads only the events after `state.last_seq` and returns the moments it found plus the state to resume from. A live worker calls it as events arrive. A test shows that detecting a match in pieces finds exactly the moments that detecting it at once does.

## Not yet detected

- `momentum_swing` and `tactical_shift` exist in the contract but have no rules yet. In 15-minute windows, field tilt and momentum swing by ±0.5 in ordinary play. They need their own calibration before they can say anything true.
