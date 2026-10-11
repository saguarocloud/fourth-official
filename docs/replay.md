# Replay and the live feed

The demo plays its matchday as if it were live (`services/replay`). The API serves each match's feed to the control room (`apps/api`).

## Replay

`replay(record, log, explainer)` publishes a match into its `FeedLog`.

| What happens | How |
|---|---|
| Events play at their own pace | Gaps between event timestamps are divided by `speed` (default 8×; the API reads `REPLAY_SPEED`, from 1 to 120), and long pauses such as half-time are capped at 30 s. |
| Moments are detected as play goes on | Incremental detection every 10 events, and immediately on a goal. Pieces give exactly the moments the whole match would, so batching only delays when a moment is published, never which. |
| Each moment is explained | Concurrently (3 at a time) by the explainer, so a slow model never holds up the match. A verified insight is published with its verdict, its code-rendered text and every attempt. |
| The clock and score are published | At least every match minute, and on every goal, moment or correction. The score leaves out goals voided by corrections in force at that moment. |
| Corrections are published when issued | A VAR void at its decision, a scorer reassignment after the final whistle. |

The feed is a wire contract (`FeedEntry`, `packages/contracts/schemas/feed-entry.schema.json`): `clock`, `moment`, `insight` and `correction` entries. Each entry is numbered (`entrySeq`), so a client resumes after the last one it has.

## Matchday

`Matchday` replays every match of the demo matchday together.
- **Spend guards:** a run spends model tokens. Only one runs at a time, runs start at most once per cooldown (15 minutes, counted from the start of the last run), and no more than 24 start in any 24 hours (`MATCHDAY_RUNS_PER_DAY` lowers that ceiling; the deployment sets 6 to keep worst-case model spend inside the budget). The guards read when runs started from a `StartLedger`, and the API runs as one replica, which a policy test pins. The default ledger is in memory, which is enough while the API explains with templates (free). With the Analyst on, the API refuses to start without a durable ledger: `START_LEDGER_URL` names one blob in Azure Storage, reached with the app's managed identity (no keys or signatures). A start is claimed atomically: the ledger reads the starts, the guards check them, and the new start is written only if the blob is still the version read (an ETag precondition), so a start recorded elsewhere in between, say by an overlapping revision during a deploy, makes this one lose with `409` instead of both running. An unreadable or unreachable ledger stops every start: `GET` and `POST /api/matchday` answer `503` and the cause is logged, never shown.
- **Robust runs:** a moment whose explanation fails is logged and the match carries on. However a run ends, no explanation outlives it. A run that crashes reports `failed`.
- **One feed per match, reset per run:** each run starts a new generation of the same feed, waking every reader, so a page opened before the run started follows it.
- **Explainer choice:** with Foundry configured (`FOUNDRY_PROJECT_ENDPOINT`, `MATCH_DATA_URL` and the agents identity's `AZURE_CLIENT_ID`), moments are explained by the Analyst (`docs/explain.md`). Without it, they are explained by the deterministic templates alone, at no cost.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/matches` | Each match's clubs, state (`idle`, `running`, `finished`) and number of feed entries |
| `GET /api/matchday` | Whether a run may start now: `ready`, `blockedBy` (`running`, `cooldown` or `daily_limit`), a `reason` safe to show, and `readyAt` (UTC, ISO 8601) when known. When the cooldown ends inside a spent day, the day decides: `readyAt` is when both allow a start |
| `POST /api/matchday` | `202` when the replay starts; `409` while one runs, during the cooldown or beyond the daily budget; `403` without the `X-Requested-By: fourth-official` header or from a foreign browser origin (a cross-site form cannot set the header, and the API grants no CORS) |
| `GET /api/matches/{id}/feed?after=n` | The run's generation, the entries after `n` (at most 1000), whether more remain, and whether the run is finished |
| `GET /api/matches/{id}/stream` | Server-sent events: one event per entry (`id` = `generation:entrySeq`, `event` = kind, `data` = the entry), a `reset` event when a new run starts, an `end` event when the run is finished, and a heartbeat every 15 s. It resumes after `Last-Event-ID` only within the same run; an ID from another run, or an unreadable one, starts from the top. It ends when the run is finished, or after 30 minutes (reconnect to continue). At most 200 streams are open at once; beyond that, `503`. |

The web app's proxy lets one client (by the address the ingress appends) hold at most 6 live streams at a time, so nobody can take every stream the API allows; beyond that it answers `429` with `Retry-After`.

| `GET /api/tenants` | The broadcast partners: id, display name, locale and disclosure mode |
| `GET /api/tenants/{tenant}/matches/{id}/feed?after=n` | A partner's feed. It holds the shared clock and corrections, plus that partner's items and no other partner's. Pages and ids are the match feed's own |
| `GET /api/tenants/{tenant}/matches/{id}/stream` | The same as server-sent events. Ids stay the match feed's own, so resuming works as above |

Responses are never cached. Insight text arrives rendered by code: clients show it as plain text.


## Partners

Every match also publishes each broadcast partner's items (`partners.py`) as `tenant_item` entries:
- **Insights.** Each verified insight is localised for every partner concurrently, then:
  - routed to an editor where the partner's policy says so (`pending_approval`, off air);
  - labelled as its disclosure mode requires;
  - timed by the director (`fourth_official_broadcast`).
- **Corrections.** Each correction airs as a strap for every partner, in its language. A correction is never held.
- **The score.** Each change of score updates every partner's score bug: kick-off, goals, and the score after a VAR void.

A failure for one partner is logged and stays with that partner: the others and the match carry on. Each match of each run starts with fresh director schedules. With the Analyst on, the Localizer runs on the `fast` model for each non-English partner, about two small calls per insight. Without Foundry, partners receive their templates.
