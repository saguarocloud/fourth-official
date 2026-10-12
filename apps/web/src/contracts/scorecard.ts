/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */

export type Analystprompt = string;
export type Localizerprompt = string;
/**
 * @maxItems 8
 */
export type Models = string[];
export type Name = string;
export type Claimid = string;
/**
 * @maxItems 64
 */
export type Eventids = string[];
export type Itemid = string;
export type Matchid = string;
/**
 * @minItems 1
 * @maxItems 8
 */
export type Reasons = [string, ...string[]];
export type Text = string;
/**
 * @maxItems 200
 */
export type Failures = FailedClaim[];
export type Firstmatch = string;
export type Generatedat = string;
export type Matches = number;
export type Hit = number;
export type Of = number;
export type Costusd = number | null;
export type P50 = number;
export type P95 = number;
export type Policyviolations = number;

export interface Scorecard {
  configuration: Configuration;
  failures: Failures;
  firstMatch: Firstmatch;
  generatedAt: Generatedat;
  matches: Matches;
  metrics: Metrics;
}
/**
 * What was run: the prompts the agents used and the model deployments they drafted on.
 */
export interface Configuration {
  analystPrompt: Analystprompt;
  localizerPrompt: Localizerprompt;
  models: Models;
  name: Name;
}
/**
 * A claim on air at full time that the ground truth does not support, and why.
 */
export interface FailedClaim {
  claimId: Claimid;
  eventIds: Eventids;
  itemId: Itemid;
  matchId: Matchid;
  reasons: Reasons;
  text: Text;
}
export interface Metrics {
  correctionsCarried: Ratio;
  costUsd: Costusd;
  firstAttemptPass: Ratio;
  keyMomentPrecision: Ratio;
  latencyMs: Latency | null;
  modelWritten: Ratio;
  policyViolations: Policyviolations;
  storylineRecall: Ratio;
  supportedClaims: Ratio;
  verifierCatch: Ratio;
}
/**
 * `hit` of `of` cases, for example 45 of 50 planted storylines surfaced.
 */
export interface Ratio {
  hit: Hit;
  of: Of;
}
export interface Latency {
  p50: P50;
  p95: P95;
}
