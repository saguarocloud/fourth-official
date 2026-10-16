/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */

export type Late = number;
export type Of = number;
export type Targetms = number;
export type Withinpercent = number;
export type Generatedat = string;
export type Correcteditems = number;
export type Count = number;
export type P50Ms = number | null;
export type P95Ms = number | null;
export type Eventsplayed = number;
export type Hit = number;
export type Of1 = number;
export type Matchid = string;
export type Modelerrors = number;
export type Moments = number;
export type Held = number;
export type Items = number;
export type Tenantid = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";
/**
 * @maxItems 8
 */
export type Partners = PartnerOperations[];
export type Runms = number;
export type State = "idle" | "running" | "finished" | "failed";
/**
 * @maxItems 100
 */
export type Matches = MatchOperations[];
export type Key = "on_air_p50" | "on_air_p95" | "correction_p95";
export type Measuredms = number | null;
export type Targetms1 = number;
/**
 * @maxItems 8
 */
export type Objectives = Objective[];

/**
 * The matchday's operations: objectives, the error budget, and each match.
 */
export interface OperationsReport {
  budget: ErrorBudget;
  generatedAt: Generatedat;
  matches: Matches;
  objectives: Objectives;
  onAir: Spread;
}
/**
 * The on-air objective as a share of items: `within_percent` of items aired without an
 * editor go on air within `target_ms`. Items later than that spend the budget.
 */
export interface ErrorBudget {
  late: Late;
  of: Of;
  targetMs: Targetms;
  withinPercent: Withinpercent;
}
/**
 * One match of the current matchday run.
 */
export interface MatchOperations {
  correctedItems: Correcteditems;
  corrections: Spread;
  eventsPlayed: Eventsplayed;
  explain: Spread;
  fallbacks: Ratio;
  firstPass: Ratio;
  matchId: Matchid;
  modelDrafts: Ratio;
  modelErrors: Modelerrors;
  moments: Moments;
  partners: Partners;
  runMs: Runms;
  state: State;
}
/**
 * How many durations were measured, and their median and 95th percentile.
 */
export interface Spread {
  count: Count;
  p50Ms: P50Ms;
  p95Ms: P95Ms;
}
/**
 * `hit` of `of` cases, for example 45 of 50 planted storylines surfaced.
 */
export interface Ratio {
  hit: Hit;
  of: Of1;
}
/**
 * One partner's items in one match: how many it published, how many it held for its editor,
 * and, for the ones it aired without one, how long from the event to air.
 */
export interface PartnerOperations {
  held: Held;
  items: Items;
  onAir: Spread;
  tenantId: Tenantid;
  withinTarget: Ratio;
}
/**
 * A service level objective: its target and what was measured against it.
 */
export interface Objective {
  key: Key;
  measuredMs: Measuredms;
  targetMs: Targetms1;
}
