# Simulator

The simulator generates the synthetic Meridian League matches that feed the whole pipeline (stage one, Ingest). It is deterministic: the same setup and seed always produce exactly the same events. That makes it a test harness as much as a data source.

## Model

- **Squads** (`squads.py`): 8 fictional clubs × 25 players (3 goalkeepers, 8 defenders, 8 midfielders, 6 forwards) with conventional shirt numbers. Names come from broad international pools. Each club draws surnames from its own disjoint slice of the pool, so no name repeats across the league, and the pools exclude the surnames of famous real footballers (`data/blocklist-names.txt`). Tests enforce both rules.
- **Team style** (`style.py`): four dials (pressing, directness, width, tempo) that shape behaviour. Storylines change them over time, so tactical shifts appear in the data.
- **Pitch** (`pitch.py`): the engine reasons in an attacking frame (progress 0 to 1 towards the opponent's goal) and writes pitch coordinates in metres on a 105 × 68 m pitch, with teams switching ends at half time.
- **Probabilities** (`probabilities.py`):
  - A logistic expected-goals model (distance, angle, header, pressure) and a logistic pass-completion model (distance, pressure, pass kind), with documented, hand-calibrated coefficients.
  - Action choice by zone and style.
- **Engine** (`engine/`): a possession-chain simulation split into four modules.
  - `state.py`: frozen state and the emitter that stamps every event.
  - `restarts.py`: possession changes, set pieces, substitutions.
  - `actions.py`: pressing, fouls, passing, carrying, shooting.
  - `match.py`: halves, kick-offs, added time; `play()` returns events, corrections and ground truth.
  - `scripted.py`: storyline moments and the corrections and ground truth they leave.
- **Phases**: each phase, the player on the ball may be pressed and may be fouled, then passes, carries, crosses or shoots. The ball is struck from where it actually is. Open play rarely gets closer than about 8 m from goal, near goal play turns lateral (cut-backs), and crosses reach 5 to 12 m.
- **Football rules the tests enforce in every match**:
  - A foul in the box is a penalty (defenders rarely risk one), never a free kick.
  - Substitutions happen only at dead balls, never take off the player on the ball, and a substitute is never substituted again.
  - Players who were sent off or substituted appear in no later event.
  - Possession changes hands only through a `POSSESSION_CHANGE` event.
  - The receiver of a completed pass is the next player on the ball.
  - A goal is assisted by the completed pass that set the scorer up (one dribble allowed); set pieces and turnovers end the move.
  - Headers mostly follow crosses.
  - Half time lasts exactly 15 minutes of wall-clock time, whatever the added time.
- **State**: the match state is frozen and advanced by pure step functions; only the seeded random generator is stateful. A test confirms the same match is produced byte for byte in a fresh process under a different hash seed.
- **Formation** selects the starting eleven (who plays). It does not yet shape positions on the pitch; tracking frames will.
- **Output**: a tuple of validated contract events (`fourth_official_contracts.MatchEvent`) with strictly increasing `seq` and non-decreasing wall-clock time.

## Realism

Calibrated on 200 seeded matches (seeds 5000–5199, `tests/matches.py` setup) against public aggregate norms for top-flight football. Other seed ranges differ by normal sampling noise of roughly 5–10%. `tests/test_engine.py` checks 60 matches against tight bounds and three style extremes against broad ones.

| Statistic (per match, 200 seeds) | Calibration | Test bound (60 seeds) |
|---|---|---|
| Passes | 970 | 880–1,060 |
| Pass completion | 79.5% | 76–83% |
| Shots | 24.2 | 20–28 |
| Shots on target | 38% | 32–44% |
| Goals | 2.71 | 2.2–3.3 |
| Goals assisted | 81% (generous: a pass plus one dribble counts; real figures are about 70–75%) | 65–90% |
| Fouls | 22.3 | 18–27 |
| Cards | 3.9 | 2.8–5 |
| Sendings-off | 0.12 | ≤ 0.3 |
| Penalties | 0.44 | — |
| Offsides | about 4.5 | 2.5–7 |

Only public aggregate knowledge informs the calibration; no real match data is used.

## Storylines

A storyline (`storylines.py`) lays scripted moments over an otherwise ordinary match. The pipeline must then notice them, explain them and, when a correction arrives, fix what it already published. Each directive does two things: it plays its football into the event stream, and it writes a ground-truth record.

| Directive | In the event stream | Ground truth |
|---|---|---|
| `ScriptedGoal(club, minute)` | The side wins the ball if needed (a possession change and an interception). Then comes a completed pass into the box, a shot from where the pass arrived, the goal (assisted by the passer), and a kick-off. | `goal`, with the pass, shot and goal events |
| `StyleShift(club, minute, …dials)` | From that minute the club plays with the new dials. A press that collapses produces visibly fewer `PRESSURE` events. | `pressing_collapse` or `pressing_surge`, with the metric and the direction a good analyst would see move (`pressing_intensity`, down or up). Shifts that don't change pressing are recorded as `tactical_shift`. |
| `VarVoid(club, goal_minute, reason)` | `VAR_CHECK` 20 s after the goal. `VAR_DECISION` (overturned) 65–90 s after the goal, long enough that items about the goal have gone out. The score reverts, and the defending side restarts with a free kick. | `var_overturn`, with the goal, check and decision events and the `EVENT_VOIDED` correction issued at the decision |
| `ScorerReassigned(club, goal_minute)` | Nothing during play. 25 minutes after the final whistle, an `EVENT_AMENDED` correction credits the goal to another outfield player who was on the pitch, as an accreditation panel does for a deflection. | `scorer_reassigned`, with the goal and the correction |
| `RedCard(club, minute)` | A foul by a player of the club, a red card, and a free kick to the opponents. This happens whichever side has the ball. The player takes no further part. | `red_card`, with the foul and the card |

- With `natural_goals=False`, only scripted goals go in. Any other shot that would have scored is saved instead, so the scoreline is exactly the script.
- A storyline is checked when it is built:
  - Scripted minutes run from 1 to 89, and never 45.
  - Moments are at least three minutes apart.
  - Every void or reassignment points at a scripted goal.
  - A voided goal cannot also be reassigned.
- `play()` refuses a storyline that names a club not in the match.
- Correction IDs are unique across matches: `c-` plus the match number, then a two-digit counter (`c-004201`).
- A match without a storyline is byte-for-byte the match the engine produced before storylines existed. A test pins this, so the calibration above still holds.

### Ground truth

Ground truth is a wire contract (`GroundTruth`, `packages/contracts/schemas/ground-truth.schema.json`). It holds:
- the storylines in the order they happened;
- the event and correction IDs that prove each one;
- the final score after corrections.

The Proving Ground scores the pipeline against it, and nothing in the live pipeline reads it. The minute recorded is when the moment really happened. Moments start once play is within a minute of the scripted minute, so they land in it unless a single preceding phase overran by more than a minute.

### Demo matchday

The demo plays the same three matches every time (`demo.py`). Their ground truth is committed in `eval/ground-truth/`, and a test fails if it goes stale; regenerate it with `make demo-truth`.

| Match | Seed | Storyline | Corrections |
|---|---|---|---|
| m42 Harbour City v Northgate FC (featured) | 4207 | HCY score 12'; NGT's high press collapses from 61'; HCY "goal" 67' ruled out for offside; NGT equalise 78'; HCY winner 89' | `EVENT_VOIDED` about 90 s after the 67' goal; the winner's scorer reassigned after full time |
| m43 Kingsbridge Athletic v Ashford Vale | 1311 | KBA red card 38'; KBA switch to direct play 40'; ASV lead 52'; ten-man KBA come back 81', 88' | none |
| m44 Calder Town v Westmere | 2718 | High-tempo, high-press, goalless chaos; goalkeepers make every save | metric restatement (planned) |

## Next

- Metric restatement corrections (the third demo match).
- 5 Hz tracking frames.
- Publishing to Azure Event Hubs.
