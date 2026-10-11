# Replay and the live feed

The demo plays its matchday as if it were live (`services/replay`). The API serves each match's feed to the control room (`apps/api`).

## Replay

`replay(record, log, explainer)` publishes a match into its `FeedLog`.

| What happens | How |
|---|---|
| Events play at their own pace | Gaps between event timestamps are divided by `speed` (default 8×), and long pauses such as half-time are capped at 30 s. |
| Moments are detected as play goes on | Incremental detection every 10 events, and immediately on a goal. Pieces give exactly the moments the whole match would, so batching only delays when a moment is published, never which. |
| Each moment is explained | Concurrently (3 at a time) by the explainer, so a slow model never holds up the match. A verified insight is published with its verdict, its code-rendered text and every attempt. |
| The clock and score are published | At least every match minute, and on every goal, moment or correction. The score leaves out goals voided by corrections in force at that moment. |
| Corrections are published when issued | A VAR void at its decision, a scorer reassignment after the final whistle. |

The feed is a wire contract (`FeedEntry`, `packages/contracts/schemas/feed-entry.schema.json`): `clock`, `moment`, `insight` and `correction` entries. Each entry is numbered (`entrySeq`), so a client resumes after the last one it has.

## Matchday

`Matchday` replays every match of the demo matchday together.
- **Spend guards:** a run spends model tokens. Only one runs at a time, runs start at most once per cooldown (15 minutes, counted from the start of the last run), and no more than 24 start in any 24 hours. The guards read when runs started from a `StartLedger`, and the API runs as one replica, which a policy test pins. The default ledger is in memory, which is enough while the API explains with templates (free). Before the Analyst spends real tokens in a deployment, the ledger must be durable: a replica that scales to zero would otherwise forget its starts.
- **Robust runs:** a moment whose explanation fails is logged and the match carries on. However a run ends, no explanation outlives it. A run that crashes reports `failed`.
- **One feed per match, reset per run:** each run starts a new generation of the same feed, waking every reader, so a page opened before the run started follows it.
- **Explainer choice:** with Foundry configured (`FOUNDRY_PROJECT_ENDPOINT`, `MATCH_DATA_URL` and the agents identity's `AZURE_CLIENT_ID`), moments are explained by the Analyst (`docs/explain.md`). Without it, they are explained by the deterministic templates alone, at no cost.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/matches` | Each match's clubs, state (`idle`, `running`, `finished`) and number of feed entries |
| `POST /api/matchday` | `202` when the replay starts; `409` while one runs, during the cooldown or beyond the daily budget; `403` without the `X-Requested-By: fourth-official` header or from a foreign browser origin (a cross-site form cannot set the header, and the API grants no CORS) |
| `GET /api/matches/{id}/feed?after=n` | The run's generation, the entries after `n` (at most 1000), whether more remain, and whether the run is finished |
| `GET /api/matches/{id}/stream` | Server-sent events: one event per entry (`id` = `generation:entrySeq`, `event` = kind, `data` = the entry), a `reset` event when a new run starts, and a heartbeat every 15 s. It resumes after `Last-Event-ID` only within the same run; an ID from another run, or an unreadable one, starts from the top. It ends when the run is finished, or after 30 minutes (reconnect to continue). At most 200 streams are open at once; beyond that, `503`. |

Responses are never cached. Insight text arrives rendered by code: clients show it as plain text.
