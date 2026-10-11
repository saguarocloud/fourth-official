# Simulator

The simulator generates the synthetic Meridian League matches that feed the whole pipeline (stage one, Ingest). It is deterministic: the same setup and seed always produce exactly the same events. That makes it a test harness as much as a data source.

## Model

- **Squads** (`squads.py`): 8 fictional clubs × 25 players (3 goalkeepers, 8 defenders, 8 midfielders, 6 forwards) with conventional shirt numbers. Names come from broad international pools. Each club draws surnames from its own disjoint slice of the pool, so no name repeats across the league, and the pools exclude the surnames of famous real footballers (`data/blocklist-names.txt`). Tests enforce both rules.
- **Team style** (`style.py`): four dials (pressing, directness, width, tempo) that shape behaviour. Storylines change them over time, so tactical shifts appear in the data.
- **Pitch** (`pitch.py`): the engine reasons in an attacking frame (progress 0 to 1 towards the opponent's goal) and writes pitch coordinates in metres on a 105 × 68 m pitch, with teams switching ends at half time.
- **Probabilities** (`probabilities.py`):
  - A logistic expected-goals model (distance, angle, header, pressure) and a logistic pass-completion model (distance, pressure, pass kind), with documented, hand-calibrated coefficients.
  - Action choice by zone and style.
- **Engine** (`engine.py`): a possession-chain simulation.
  - Each phase, the player on the ball may be pressed, may be fouled (with cards and free kicks), then passes, carries, crosses or shoots.
  - Outcomes produce interceptions, tackles, offsides, throw-ins, saves, corners, goal kicks and goals (assisted when they follow straight from a completed pass).
  - Each team makes three substitutions; a sent-off player takes no further part; added time is random per half.
  - The match state is frozen and advanced by pure step functions; only the seeded random generator is stateful.
- **Output**: a tuple of validated contract events (`fourth_official_contracts.MatchEvent`) with strictly increasing `seq` and non-decreasing wall-clock time.

## Realism checks

`tests/test_engine.py` simulates 30 matches and checks per-match averages against public aggregate norms for top-flight football, using generous bounds:

| Statistic (per match) | Bound | Current calibration |
|---|---|---|
| Passes | 650–1,150 | about 1,080 |
| Pass completion | 72–88% | about 78% |
| Shots | 18–32 | about 25 |
| Shots on target | 25–45% | about 38% |
| Goals | 1.8–3.8 | about 2.8 |
| Cards | 1.5–6 | about 3.2 |

Fouls (about 24), offsides (about 5) and saves are consistent with these. Only public aggregate knowledge informs the calibration; no real match data is used.

## Next

- Storylines and ground truth: scripted goals, style changes (a press that fades after the hour), red cards, VAR voids and scorer reassignments, each written as machine-checkable ground truth for the Proving Ground.
- 5 Hz tracking frames.
- Publishing to Azure Event Hubs.
