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

- **Validation:** arguments are checked strictly against their schemas (patterns, ranges, enumerations, no type coercion, unknown arguments refused) before a tool runs. Errors may name the argument at fault, but never repeat a value the caller sent. Store refusals are fixed messages.
- **Output schemas:** every tool returns a typed contract model and publishes its output schema.
- **Pages:** `get_events` returns at most 100 events and the seq to continue from.
- **Voids:** a voided goal leaves the score from the VAR decision that overturned it, never earlier. Scorer amendments issued after the final whistle are corrections for the correction cascade; the event stream keeps events as first published.
- **HTTP:** the server binds loopback by default. In a container it binds all interfaces and accepts only loopback and the host names it is served under (`--allowed-host`, or `MATCH_DATA_ALLOWED_HOSTS`, comma-separated), which guards against DNS rebinding. In Azure it sits behind the Container Apps environment's internal ingress: only apps in the environment can reach it, never the internet. `GET /healthz` answers on any host, so the platform's probes reach it by address, and reports the release from `APP_VERSION`.
- **Tested promise:** a test checks that under any live position, every snapshot and moment served equals what the published events alone give.
- **Numbers:** all numbers come from the stats engine. An agent quotes them by snapshot ID in claim markup (ADR-006) and never recomputes them.
- **Store:** the demo store replays the fixed matchday in memory. A store backed by Cosmos DB will implement the same `MatchStore` interface.

Run it locally:

```bash
uv run python -m fourth_official_match_data           # stdio, for a local agent
uv run python -m fourth_official_match_data --http    # streamable HTTP on 127.0.0.1:8100
```
