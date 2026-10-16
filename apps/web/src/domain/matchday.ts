/**
 * The Control Room's model: each match on the wall, the latest items, the latest correction and
 * the matchday's headline figures, as the API computed them from the feeds (`controlRoom.ts`
 * maps the reports onto it). Everything here is fictional: the Meridian League, its clubs and its
 * broadcast partners do not exist.
 */

import type { ItemState } from "@/components/ui/StatusLamp";

import type { PartnerId } from "./broadcast";

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

export interface Club {
  readonly code: string;
  readonly name: string;
}

export type MatchStatus = "not_started" | "live" | "full_time";

/** Elapsed time within a period, as on the broadcast clock. */
export interface Clock {
  readonly period: 1 | 2;
  readonly minute: number;
  readonly second: number;
}

export interface Match {
  readonly id: string;
  readonly home: string;
  readonly away: string;
  readonly homeScore: number;
  readonly awayScore: number;
  /** None before kick-off. */
  readonly clock: Clock | null;
  readonly status: MatchStatus;
  readonly featured: boolean;
  /** Partner items a minute of the run so far; none before it started. */
  readonly itemsPerMinute: number | null;
  readonly pendingApprovals: number;
  readonly corrections: number;
  /** Event to air at the 95th percentile, as measured; none before anything aired. */
  readonly p95LatencyMs: number | null;
  /** Partners with a graphic on screen now. */
  readonly onAir: readonly PartnerId[];
}

export interface ActivityEntry {
  readonly id: string;
  /** Order across the matchday; higher is newer. */
  readonly sequence: number;
  readonly matchId: string;
  /** Football minute as broadcast (68:03 elapsed is the 69th minute). */
  readonly minute: number;
  readonly period: 1 | 2;
  readonly partnerId: PartnerId | null;
  readonly state: ItemState;
  readonly text: string;
  /** Written by a model (then verified), as opposed to filled from a deterministic template. */
  readonly aiGenerated: boolean;
}

export interface Correction {
  readonly matchId: string;
  readonly reason: string;
  /** Match clock of the corrected event, e.g. "67:12" (unknown: "–"). */
  readonly eventAt: string;
  /** Match clock when the correction was received, e.g. "68:03". */
  readonly receivedAt: string;
  readonly published: string;
  readonly corrected: string;
  readonly itemsCorrected: number;
  readonly partners: number;
  readonly languages: number;
  /** How long the corrections desk took; none before it reported. */
  readonly elapsedMs: number | null;
}

export interface MatchdaySummary {
  readonly liveMatches: number;
  readonly pendingApprovals: number;
  readonly corrections: number;
  /** Event to air at the 95th percentile across the run; none before anything aired. */
  readonly p95LatencyMs: number | null;
  /** The on-air objective; none when operations could not be read. */
  readonly sloMs: number | null;
  readonly withinSlo: boolean;
  readonly costMicrousd: number;
}

export function clubByCode(code: string): Club {
  return CLUBS[code as keyof typeof CLUBS] ?? { code, name: code };
}

export interface Verdict {
  readonly tone: "green" | "amber" | "red" | "neutral";
  readonly text: string;
}

/** The five-second reading of the whole matchday, most serious condition first. */
export function matchdayVerdict(summary: MatchdaySummary): Verdict {
  if (!summary.withinSlo) {
    return {
      tone: "red",
      text: "Event-to-air latency is outside the SLO. Investigate before more items publish.",
    };
  }
  const matches =
    summary.liveMatches === 0
      ? "No matches live."
      : summary.liveMatches === 1
        ? "The live match is under control."
        : `All ${summary.liveMatches} matches under control.`;
  if (summary.pendingApprovals > 0) {
    const items =
      summary.pendingApprovals === 1
        ? "1 item awaits approval."
        : `${summary.pendingApprovals} items await approval.`;
    return { tone: "amber", text: `${matches} ${items}` };
  }
  return {
    tone: summary.liveMatches === 0 ? "neutral" : "green",
    text: `${matches} Nothing awaits approval.`,
  };
}
