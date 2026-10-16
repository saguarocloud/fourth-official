/**
 * The Control Room, read from two live reports the API computes from the feeds: the wall (each
 * match's score, clock, partners on air, items awaiting an editor, corrections, the latest items
 * and correction) and operations (what the run measured and cost). This module checks the wall's
 * shape and maps both onto the Control Room's model; it computes nothing but sums and one rate.
 */
import type { OperationsReport } from "@/contracts/operations";
import type { ItemState } from "@/components/ui/StatusLamp";
import type { MatchdayWall, WallActivity, WallCorrection, WallMatch } from "@/contracts/wall";
import { formatMatchClock, footballMinute } from "@/lib/format";

import type { PartnerId } from "./broadcast";
import type { ActivityEntry, Correction, Match, MatchdaySummary, MatchStatus } from "./matchday";
import { totals } from "./operations";

/** The matchday's featured match: the one the demo's story follows, shown first and largest. */
export const FEATURED_MATCH = "m42";
const MS_PER_MINUTE = 60_000;

type Fields = Record<string, unknown>;
const isObject = (v: unknown): v is Fields =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isCount = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const isString = (v: unknown): v is string => typeof v === "string";
const isClock = (v: unknown): boolean =>
  isObject(v) && (v.period === 1 || v.period === 2) && isCount(v.minute) && isCount(v.second);
const isList = (v: unknown, each: (item: unknown) => boolean): boolean =>
  Array.isArray(v) && v.every(each);
const STATES = ["idle", "running", "finished", "failed"];

const isWallMatch = (v: unknown): boolean =>
  isObject(v) &&
  ["matchId", "home", "away"].every((k) => isString(v[k])) &&
  STATES.includes(v.state as string) &&
  isObject(v.score) &&
  isCount(v.score.home) &&
  isCount(v.score.away) &&
  (v.clock === null || isClock(v.clock)) &&
  ["items", "pendingApprovals", "corrections"].every((k) => isCount(v[k])) &&
  isList(v.onAir, isString);

const isActivity = (v: unknown): boolean =>
  isObject(v) &&
  isCount(v.entrySeq) &&
  ["matchId", "tenantId", "state", "headline"].every((k) => isString(v[k])) &&
  isClock(v.clock) &&
  typeof v.aiWritten === "boolean";

const isCorrection = (v: unknown): boolean =>
  isObject(v) &&
  ["matchId", "correctionId", "summary", "outText", "inText"].every((k) => isString(v[k])) &&
  (v.eventClock === null || isClock(v.eventClock)) &&
  isClock(v.receivedClock) &&
  ["itemsCorrected", "partners", "languages"].every((k) => isCount(v[k])) &&
  (v.elapsedMs === null || isCount(v.elapsedMs));

/** The API's wall, if it is shaped as one. */
export function parseWall(value: unknown): MatchdayWall | null {
  if (!isObject(value) || !isString(value.generatedAt)) return null;
  const ok =
    isList(value.matches, isWallMatch) &&
    isList(value.activity, isActivity) &&
    (value.latestCorrection === null || isCorrection(value.latestCorrection));
  return ok ? (value as unknown as MatchdayWall) : null;
}

// An item an editor rejected never airs: on the lamp it reads as dropped.
const LAMP: Readonly<Record<WallActivity["state"], ItemState>> = {
  on_air: "on_air",
  pending_approval: "pending_approval",
  rejected: "dropped",
  retracted: "retracted",
  amended: "amended",
};

const STATUS: Readonly<Record<WallMatch["state"], MatchStatus>> = {
  idle: "not_started",
  running: "live",
  finished: "full_time",
  failed: "full_time",
};

function match(wall: WallMatch, operations: OperationsReport | null): Match {
  const measured = operations?.matches.find((m) => m.matchId === wall.matchId);
  const runMs = measured?.runMs ?? 0;
  return {
    id: wall.matchId,
    home: wall.home,
    away: wall.away,
    homeScore: wall.score.home,
    awayScore: wall.score.away,
    clock: wall.clock,
    status: STATUS[wall.state],
    featured: wall.matchId === FEATURED_MATCH,
    itemsPerMinute: runMs > 0 ? (wall.items * MS_PER_MINUTE) / runMs : null,
    pendingApprovals: wall.pendingApprovals,
    corrections: wall.corrections,
    p95LatencyMs: measured?.onAir.p95Ms ?? null,
    onAir: wall.onAir as PartnerId[],
  };
}

function correction(latest: WallCorrection): Correction {
  const at = (c: { minute: number; second: number } | null) =>
    c === null ? "–" : formatMatchClock(c.minute, c.second);
  return {
    matchId: latest.matchId,
    reason: latest.summary,
    eventAt: at(latest.eventClock),
    receivedAt: at(latest.receivedClock),
    published: latest.outText,
    corrected: latest.inText,
    itemsCorrected: latest.itemsCorrected,
    partners: latest.partners,
    languages: latest.languages,
    elapsedMs: latest.elapsedMs,
  };
}

export interface ControlRoom {
  readonly matches: readonly Match[];
  readonly summary: MatchdaySummary;
  readonly activity: readonly ActivityEntry[];
  readonly latestCorrection: Correction | null;
}

/** The Control Room from the wall and, when it could be read, what operations measured. */
export function controlRoom(wall: MatchdayWall, operations: OperationsReport | null): ControlRoom {
  const matches = wall.matches
    .map((m) => match(m, operations))
    .sort((a, b) => Number(b.featured) - Number(a.featured));
  const p95 = operations?.objectives.find((o) => o.key === "on_air_p95");
  const measured = p95?.measuredMs ?? null;
  const add = (of: (m: Match) => number) => matches.reduce((n, m) => n + of(m), 0);
  const count = wall.activity.length;
  return {
    matches,
    summary: {
      liveMatches: matches.filter((m) => m.status === "live").length,
      pendingApprovals: add((m) => m.pendingApprovals),
      corrections: add((m) => m.corrections),
      p95LatencyMs: measured,
      sloMs: p95?.targetMs ?? null,
      withinSlo: measured === null || p95 === undefined || measured <= p95.targetMs,
      costMicrousd: operations ? totals(operations).totalMicrousd : 0,
    },
    activity: wall.activity.map((a, i) => ({
      id: `${a.matchId}-${a.entrySeq}`,
      sequence: count - i,
      matchId: a.matchId,
      minute: footballMinute(a.clock.minute),
      period: a.clock.period,
      partnerId: a.tenantId as PartnerId,
      state: LAMP[a.state],
      text: a.headline,
      aiGenerated: a.aiWritten,
    })),
    latestCorrection: wall.latestCorrection ? correction(wall.latestCorrection) : null,
  };
}
