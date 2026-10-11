import type { RunState } from "@/domain/live";

/** A match as the matchday API lists it. */
export interface MatchSummary {
  readonly matchId: string;
  readonly home: string;
  readonly away: string;
  readonly homeName: string;
  readonly awayName: string;
  readonly state: RunState;
  readonly entries: number;
}

/** Whether the matchday may start, as the matchday API answers it. */
export interface MatchdayAvailability {
  readonly ready: boolean;
  readonly blockedBy?: "running" | "cooldown" | "daily_limit" | null;
  /** Why not, safe to show. */
  readonly reason: string | null;
  /** ISO time from which it may start; null while a run is under way. */
  readonly readyAt: string | null;
}
