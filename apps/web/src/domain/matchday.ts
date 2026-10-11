/**
 * Matchday model for the control room. Everything here is fictional: the Meridian League, its
 * clubs and its broadcast partners do not exist.
 */

import type { ItemState } from "@/components/ui/StatusLamp";

export const CLUBS = {
  HCY: { code: "HCY", name: "Harbour City" },
  NGT: { code: "NGT", name: "Northgate FC" },
  KBA: { code: "KBA", name: "Kingsbridge Athletic" },
  ASV: { code: "ASV", name: "Ashford Vale" },
  CAL: { code: "CAL", name: "Calder Town" },
  WMR: { code: "WMR", name: "Westmere" },
  BRM: { code: "BRM", name: "Brackley Mills" },
  SLT: { code: "SLT", name: "Saltmarsh" },
} as const;

export type ClubCode = keyof typeof CLUBS;
export type Club = (typeof CLUBS)[ClubCode];

export type PartnerId = "northlight" | "tribuna-austral" | "rheinblick";

export interface Partner {
  readonly id: PartnerId;
  readonly name: string;
  readonly locale: "en-GB" | "es-MX" | "de-DE";
  readonly market: string;
}

export type MatchStatus = "live" | "half_time" | "full_time";

export interface Match {
  readonly id: string;
  readonly home: ClubCode;
  readonly away: ClubCode;
  readonly homeScore: number;
  readonly awayScore: number;
  readonly minute: number;
  readonly second: number;
  readonly period: 1 | 2;
  readonly status: MatchStatus;
  readonly featured: boolean;
  readonly itemsPerMinute: number;
  readonly pendingApprovals: number;
  readonly corrections: number;
  readonly p95LatencyMs: number;
  readonly onAir: Readonly<Record<PartnerId, boolean>>;
}

export interface ActivityEntry {
  readonly id: string;
  /** Monotonic order across the matchday; higher is newer. */
  readonly sequence: number;
  readonly matchId: string;
  readonly minute: number;
  readonly period: 1 | 2;
  readonly partnerId: PartnerId | null;
  readonly state: ItemState;
  readonly text: string;
}

export interface Correction {
  readonly matchId: string;
  readonly reason: string;
  readonly published: string;
  readonly corrected: string;
  readonly itemsCorrected: number;
  readonly partners: number;
  readonly languages: number;
  readonly elapsedMs: number;
}

export interface Matchday {
  readonly studio: string;
  readonly label: string;
  readonly sloMs: number;
  readonly costCents: number;
  readonly partners: readonly Partner[];
  readonly matches: readonly Match[];
  readonly activity: readonly ActivityEntry[];
  readonly latestCorrection: Correction | null;
}

export interface MatchdaySummary {
  readonly liveMatches: number;
  readonly itemsPerMinute: number;
  readonly pendingApprovals: number;
  readonly corrections: number;
  readonly p95LatencyMs: number;
  readonly sloMs: number;
  readonly withinSlo: boolean;
  readonly costCents: number;
}

export function clubByCode(code: ClubCode): Club {
  return CLUBS[code];
}

/** Matchday headline numbers, always derived from the matches themselves. */
export function summarise(
  matches: readonly Match[],
  { sloMs, costCents }: { readonly sloMs: number; readonly costCents: number },
): MatchdaySummary {
  const live = matches.filter((m) => m.status !== "full_time");
  const sum = (pick: (m: Match) => number) => live.reduce((total, m) => total + pick(m), 0);
  const p95LatencyMs = live.reduce((worst, m) => Math.max(worst, m.p95LatencyMs), 0);
  return {
    liveMatches: live.length,
    itemsPerMinute: sum((m) => m.itemsPerMinute),
    pendingApprovals: sum((m) => m.pendingApprovals),
    corrections: sum((m) => m.corrections),
    p95LatencyMs,
    sloMs,
    withinSlo: p95LatencyMs <= sloMs,
    costCents,
  };
}
