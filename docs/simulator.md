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
  - `match.py`: halves, kick-offs, added time.
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

Calibrated on 200 seeded matches against public aggregate norms for top-flight football. `tests/test_engine.py` checks 60 matches against tight bounds and three style extremes against broad ones.

| Statistic (per match, 200 seeds) | Calibration | Test bound (60 seeds) |
|---|---|---|
| Passes | 970 | 880–1,060 |
| Pass completion | 79.5% | 76–83% |
| Shots | 24.2 | 20–28 |
| Shots on target | 38% | 32–44% |
| Goals | 2.71 | 2.2–3.3 |
| Goals assisted | 81% | 65–90% |
| Fouls | 22.3 | 18–27 |
| Cards | 3.9 | 2.8–5 |
| Sendings-off | 0.12 | ≤ 0.3 |
| Penalties | 0.44 | — |
| Offsides | about 4.5 | 2.5–7 |

Only public aggregate knowledge informs the calibration; no real match data is used.

## Next

- Storylines and ground truth: scripted goals, style changes (a press that fades after the hour), red cards, VAR voids and scorer reassignments, each written as machine-checkable ground truth for the Proving Ground.
- 5 Hz tracking frames.
- Publishing to Azure Event Hubs.
