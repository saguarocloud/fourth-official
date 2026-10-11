# fourth-official-simulator

Deterministic synthetic match simulator for the fictional Meridian League. See [docs/simulator.md](../../docs/simulator.md).

```python
from datetime import UTC, datetime
from fourth_official_simulator.engine import MatchSetup, TeamSetup, simulate
from fourth_official_simulator.squads import generate_squad
from fourth_official_simulator.style import TeamStyle

style = TeamStyle(pressing=0.7, directness=0.4, width=0.6, tempo=0.6)
events = simulate(
    MatchSetup(
        match_id="m42",
        seed=4207,
        kickoff=datetime(2026, 10, 24, 14, 0, tzinfo=UTC),
        home=TeamSetup(squad=generate_squad("HCY", seed=1), formation="4-3-3", style=style),
        away=TeamSetup(squad=generate_squad("NGT", seed=1), formation="4-2-3-1", style=style),
    )
)
```
