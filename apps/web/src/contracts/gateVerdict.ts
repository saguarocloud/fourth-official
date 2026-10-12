/* Generated from packages/contracts/schemas by `npm run contracts`. Do not edit. */

export type Allowed = boolean;
export type Baseline = string;
export type Candidate = string;
/**
 * @minItems 1
 * @maxItems 16
 */
export type Checks = [GateCheck, ...GateCheck[]];
export type Detail = string;
export type Passed = boolean;
export type Rule =
  | "unsupported_claims"
  | "policy_violations"
  | "verifier_catch"
  | "corrections_carried"
  | "storyline_recall"
  | "model_written"
  | "latency_p95";

/**
 * The Release Gate's answer for a candidate against the baseline: allowed only if every
 * rule passes.
 */
export interface GateVerdict {
  allowed: Allowed;
  baseline: Baseline;
  candidate: Candidate;
  checks: Checks;
}
export interface GateCheck {
  detail: Detail;
  passed: Passed;
  rule: Rule;
}
