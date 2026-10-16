/**
 * Operations: the matchday run as the API measured it (ADR-016), read as a statement of service:
 * how the run did against its service levels, what it spent of its error budget, and what it
 * cost. The API computes every figure; this module only checks the report's shape, adds up the
 * matches' amounts, and words the verdict.
 */
import type {
  ErrorBudget,
  MatchOperations,
  Objective,
  OperationsReport,
} from "@/contracts/operations";

type Fields = Record<string, unknown>;
const isObject = (v: unknown): v is Fields =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isCount = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const isMs = (v: unknown): boolean => v === null || isCount(v);
const isString = (v: unknown): v is string => typeof v === "string";
const isPercent = (v: unknown): boolean => isCount(v) && v >= 1 && v <= 100;
const isList = (v: unknown, each: (item: unknown) => boolean): boolean =>
  Array.isArray(v) && v.every(each);
const counts = (v: unknown, keys: readonly string[]): boolean =>
  isObject(v) && keys.every((key) => isCount(v[key]));

const isRatio = (v: unknown): boolean =>
  isObject(v) && isCount(v.hit) && isCount(v.of) && v.hit <= v.of;
const isSpread = (v: unknown): boolean =>
  isObject(v) && isCount(v.count) && isMs(v.p50Ms) && isMs(v.p95Ms);
const isTokens = (v: unknown): boolean => counts(v, ["input", "output"]);

function isPartner(v: unknown): boolean {
  return (
    isObject(v) &&
    isString(v.tenantId) &&
    counts(v, ["items", "held", "costMicrousd"]) &&
    isSpread(v.onAir) &&
    isRatio(v.withinTarget) &&
    isRatio(v.withinBudget) &&
    isTokens(v.tokens) &&
    isMs(v.latencyBudgetMs)
  );
}

const MATCH_COUNTS = [
  "runMs",
  "eventsPlayed",
  "moments",
  "modelErrors",
  "correctedItems",
  "modelCostMicrousd",
  "infraCostMicrousd",
];
const STATES = ["idle", "running", "finished", "failed"];

function isMatch(v: unknown): boolean {
  return (
    isObject(v) &&
    isString(v.matchId) &&
    STATES.includes(v.state as string) &&
    counts(v, MATCH_COUNTS) &&
    [v.explain, v.onAir, v.corrections].every(isSpread) &&
    [v.firstPass, v.fallbacks, v.modelDrafts].every(isRatio) &&
    isTokens(v.tokens) &&
    isList(v.partners, isPartner)
  );
}

const isObjective = (v: unknown): boolean =>
  isObject(v) && isString(v.key) && isCount(v.targetMs) && isMs(v.measuredMs);
const isPrice = (v: unknown): boolean =>
  isObject(v) &&
  isString(v.model) &&
  counts(v, ["inputMicrousdPerMillion", "outputMicrousdPerMillion"]);

/** The API's report, if it is shaped as one. */
export function parseOperations(value: unknown): OperationsReport | null {
  if (!isObject(value) || !isString(value.generatedAt)) return null;
  const { objectives, budget, onAir, matches, pricing } = value;
  const ok =
    isList(objectives, isObjective) &&
    counts(budget, ["withinPercent", "targetMs", "late", "of"]) &&
    isPercent((budget as Fields).withinPercent) &&
    isSpread(onAir) &&
    isList(matches, isMatch) &&
    isObject(pricing) &&
    isList(pricing.models, isPrice) &&
    isCount(pricing.infraMicrousdPerHour);
  return ok ? (value as unknown as OperationsReport) : null;
}

const MICRO = 1_000_000;
const PERCENT = 100;

// The smallest amount shown: a hundredth of a cent.
const SMALLEST = 100;

/** Micro-dollars as dollars, to the hundredth of a cent (a match costs cents); an amount
 * smaller than that is said to be so, never shown as nothing. */
export const dollars = (micro: number): string =>
  micro > 0 && micro < SMALLEST ? "< $0.0001" : `$${(micro / MICRO).toFixed(4)}`;

const MS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;

/** A duration in seconds to the tenth; under a second, in whole milliseconds. */
export const seconds = (ms: number): string =>
  ms < MS_PER_SECOND ? `${ms} ms` : `${(ms / MS_PER_SECOND).toFixed(1)} s`;

/** How long a match ran: minutes and seconds, or seconds under a minute. */
export function ranFor(ms: number): string {
  const whole = Math.floor(ms / MS_PER_SECOND);
  if (whole < SECONDS_PER_MINUTE) return seconds(ms);
  return `${Math.floor(whole / SECONDS_PER_MINUTE)} min ${whole % SECONDS_PER_MINUTE} s`;
}

export interface Totals {
  readonly modelMicrousd: number;
  readonly infraMicrousd: number;
  readonly totalMicrousd: number;
  readonly tokensIn: number;
  readonly tokensOut: number;
}

const sum = (matches: readonly MatchOperations[], of: (m: MatchOperations) => number) =>
  matches.reduce((total, m) => total + of(m), 0);

/** The run's cost and tokens, every match added up. */
export function totals(report: OperationsReport): Totals {
  const modelMicrousd = sum(report.matches, (m) => m.modelCostMicrousd);
  const infraMicrousd = sum(report.matches, (m) => m.infraCostMicrousd);
  return {
    modelMicrousd,
    infraMicrousd,
    totalMicrousd: modelMicrousd + infraMicrousd,
    tokensIn: sum(report.matches, (m) => m.tokens.input),
    tokensOut: sum(report.matches, (m) => m.tokens.output),
  };
}

export interface BudgetUse {
  readonly late: number;
  readonly of: number;
  /** Late items the objective allows over the items timed so far. */
  readonly allowed: number;
  /** The share of the budget spent; null when none was allowed and some was spent anyway. */
  readonly spentPercent: number | null;
  /** More items were late than the objective allows (never hidden by rounding). */
  readonly over: boolean;
}

/** How much of the error budget the late items spent; null before any item was timed. */
export function budgetUse(budget: ErrorBudget): BudgetUse | null {
  if (budget.of === 0) return null;
  const allowed = (budget.of * (PERCENT - budget.withinPercent)) / PERCENT;
  const over = budget.late > allowed;
  let spentPercent: number | null = 0;
  if (allowed > 0) spentPercent = Math.round((budget.late / allowed) * PERCENT);
  else if (over) spentPercent = null;
  return { late: budget.late, of: budget.of, allowed, spentPercent, over };
}

/** The budget in words: how many items were late, and what share of the budget that spent. */
export function budgetWords(use: BudgetUse): string {
  let share = `${use.spentPercent}% of the error budget spent`;
  if (use.spentPercent === null) share = "with no late item allowed";
  else if (use.spentPercent > PERCENT)
    share = `the error budget spent ${timesOver(use)} times over`;
  return `${use.late} of ${use.of} items late, ${share}`;
}

/** How many times over a spent budget went, to the tenth (4.7), or whole (20). */
export function timesOver(use: BudgetUse): string {
  const times = (use.spentPercent ?? 0) / PERCENT;
  return Number.isInteger(times) ? String(times) : times.toFixed(1);
}

/** Whether an objective was met; null before anything was measured against it. */
export function objectiveMet(objective: Objective): boolean | null {
  return objective.measuredMs === null ? null : objective.measuredMs <= objective.targetMs;
}

export type Phase = "idle" | "running" | "done";

/** Whether nothing has run since the platform started, a run is under way, or it is over. */
export function phase(report: OperationsReport): Phase {
  const states = report.matches.map((m) => m.state);
  if (states.every((s) => s === "idle")) return "idle";
  return states.includes("running") ? "running" : "done";
}

export interface Verdict {
  readonly tone: "neutral" | "green" | "red";
  readonly text: string;
}

const MISSED: Readonly<Record<Objective["key"], string>> = {
  on_air_p50: "the on-air median",
  on_air_p95: "the on-air 95th percentile",
  correction_p95: "the corrections desk's 95th percentile",
};

const listed = (parts: readonly string[]): string =>
  parts.length < 2 ? (parts[0] ?? "") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;

/** The statement's first line: the service levels (each one missed, by how much), the budget,
 * and the cost, in that order. */
export function verdict(report: OperationsReport): Verdict {
  const now = phase(report);
  if (now === "idle") {
    return {
      tone: "neutral",
      text: "Nothing measured yet: no matchday has run since the platform last started. Start one from Match Live and this statement fills in as it plays.",
    };
  }
  const running = now === "running";
  const cost = dollars(totals(report).totalMicrousd);
  const spent = running ? `It has cost ${cost} so far.` : `It cost ${cost}.`;
  const use = budgetUse(report.budget);
  const p95 = report.objectives.find((o) => o.key === "on_air_p95");
  if (use === null || p95?.measuredMs == null) {
    return {
      tone: "neutral",
      text: `The matchday is running; no item has gone on air without an editor yet. ${spent}`,
    };
  }
  const budget = `${budgetWords(use)}.`;
  const missed = report.objectives.filter((o) => objectiveMet(o) === false);
  if (missed.length === 0) {
    const subject = running ? "The matchday is holding" : "The last matchday held";
    const onAir = `on air within ${seconds(p95.measuredMs)} for ${report.budget.withinPercent}% of items, against ${seconds(p95.targetMs)}`;
    return { tone: "green", text: `${subject} its service levels: ${onAir}. ${budget} ${spent}` };
  }
  const subject = running ? "The matchday is missing" : "The last matchday missed";
  const misses = missed.map(
    (o) =>
      `${MISSED[o.key] ?? o.key} (${seconds(o.measuredMs ?? 0)} against ${seconds(o.targetMs)})`,
  );
  return { tone: "red", text: `${subject} ${listed(misses)}. ${budget} ${spent}` };
}
