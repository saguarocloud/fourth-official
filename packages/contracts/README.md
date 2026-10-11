# fourth-official-contracts

Canonical wire contracts for Fourth Official: the match events the pipeline ingests and the corrections that change them after publication. See [ADR-005](../../docs/DECISIONS.md).

```python
from fourth_official_contracts import parse_match_event, parse_correction

event = parse_match_event(raw_json_dict)  # ShotEvent, PassEvent, GoalEvent, ...
correction = parse_correction(raw_json_dict)  # EventVoided or EventAmended
event.to_wire()  # canonical camelCase JSON form
```

- Models are frozen, strict and refuse unknown fields; domain rules (team membership, goal credit, references within the match, clock ranges, pitch bounds) are validated on construction.
- Wire input is parsed by camelCase alias only; Python code may construct models by field name.
- `schemas/` holds the exported JSON Schemas. Regenerate with `make contracts`; the test suite fails if they drift.
