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
  /** Match clock of the corrected event, e.g. "67:12". */
  readonly eventAt: string;
  /** Match clock when the correction was received, e.g. "68:03". */
  readonly receivedAt: string;
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
  /** Worst p95 event-to-air latency across live matches; null when nothing is live. */
  readonly p95LatencyMs: number | null;
  readonly sloMs: number;
  readonly withinSlo: boolean;
  readonly costCents: number;
}

export function clubByCode(code: ClubCode): Club {
  return CLUBS[code];
}

/**
 * Matchday headline numbers, always derived from the matches themselves. Throughput and latency
 * describe live matches; approvals and corrections stay counted after full time, because the
 * work is still open.
 */
export function summarise(
  matches: readonly Match[],
  { sloMs, costCents }: { readonly sloMs: number; readonly costCents: number },
): MatchdaySummary {
  const live = matches.filter((m) => m.status !== "full_time");
  const total = (from: readonly Match[], pick: (m: Match) => number) =>
    from.reduce((sum, m) => sum + pick(m), 0);
  const p95LatencyMs = live.length === 0 ? null : Math.max(...live.map((m) => m.p95LatencyMs));
  return {
    liveMatches: live.length,
    itemsPerMinute: total(live, (m) => m.itemsPerMinute),
    pendingApprovals: total(matches, (m) => m.pendingApprovals),
    corrections: total(matches, (m) => m.corrections),
    p95LatencyMs,
    sloMs,
    withinSlo: p95LatencyMs === null || p95LatencyMs <= sloMs,
    costCents,
  };
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
