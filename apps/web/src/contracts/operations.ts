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
export type Infracostmicrousd = number;
export type Matchid = string;
export type Modelcostmicrousd = number;
export type Modelerrors = number;
export type Moments = number;
export type Costmicrousd = number;
export type Held = number;
export type Items = number;
export type Latencybudgetms = number | null;
export type Tenantid = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";
export type Input = number;
export type Output = number;
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
export type Inframicrousdperhour = number;
export type Inputmicrousdpermillion = number;
export type Model = string;
export type Outputmicrousdpermillion = number;
/**
 * @maxItems 8
 */
export type Models = ModelPrice[];

/**
 * The matchday's operations: objectives, the error budget, and each match.
 */
export interface OperationsReport {
  budget: ErrorBudget;
  generatedAt: Generatedat;
  matches: Matches;
  objectives: Objectives;
  onAir: Spread;
  pricing: Pricing;
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
  infraCostMicrousd: Infracostmicrousd;
  matchId: Matchid;
  modelCostMicrousd: Modelcostmicrousd;
  modelDrafts: Ratio;
  modelErrors: Modelerrors;
  moments: Moments;
  onAir: Spread;
  partners: Partners;
  runMs: Runms;
  state: State;
  tokens: TokenUse;
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
  costMicrousd: Costmicrousd;
  held: Held;
  items: Items;
  latencyBudgetMs: Latencybudgetms;
  onAir: Spread;
  tenantId: Tenantid;
  tokens: TokenUse;
  withinBudget: Ratio;
  withinTarget: Ratio;
}
/**
 * Tokens model calls spent, as the service reported them.
 */
export interface TokenUse {
  input: Input;
  output: Output;
}
/**
 * A service level objective: its target and what was measured against it.
 */
export interface Objective {
  key: Key;
  measuredMs: Measuredms;
  targetMs: Targetms1;
}
/**
 * The prices the report's costs were computed with.
 */
export interface Pricing {
  infraMicrousdPerHour: Inframicrousdperhour;
  models: Models;
}
/**
 * What a model deployment's tokens cost, in micro-dollars per million tokens.
 */
export interface ModelPrice {
  inputMicrousdPerMillion: Inputmicrousdpermillion;
  model: Model;
  outputMicrousdPerMillion: Outputmicrousdpermillion;
}
