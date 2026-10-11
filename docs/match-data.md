# Match Data MCP server

Agents read the match through an MCP server (`services/match-data`), never directly from storage. Every tool is **read-only** and **closed-world** (`readOnlyHint`, `openWorldHint: false`). Every tool is also **time-bounded**: answers come from the match as published so far, and asking for any later point is refused. The refusal is the same however far ahead the request is, so it never reveals how long the match runs.

| Tool | Returns |
|---|---|
| `list_matches` | The matchday's matches, clubs and live position |
| `get_match_state` | The score (without goals voided by corrections issued so far), clock and clubs at a moment |
| `get_metric` | A metric snapshot: value, window, moment and the exact events it was computed from |
| `compare_windows` | The last five minutes against the fifteen before them, the comparison behind shift moments |
| `get_events` | Published events in a seq range, at most 100, optionally filtered by type |
| `get_player` | A player's name, club, shirt and position |
| `list_moments` | Moments found so far, each with its evidence |

- **Validation:** arguments are checked against their schemas (patterns, ranges, enumerations) before a tool runs. Refusals are tool errors that name the problem without echoing the input.
- **Numbers:** all numbers come from the stats engine. An agent quotes them by snapshot ID in claim markup (ADR-006) and never recomputes them.
- **Store:** the demo store replays the fixed matchday in memory. A store backed by Cosmos DB will implement the same `MatchStore` interface.

Run it locally:

```bash
uv run python -m fourth_official_match_data           # stdio, for a local agent
uv run python -m fourth_official_match_data --http    # streamable HTTP on 127.0.0.1:8100
```
