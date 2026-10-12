/**
 * The Proving Ground: the recorded runs the API serves and the Release Gate's verdict on them
 * (ADR-014), read as a go/no-go poll. The verdict itself is the server's: this module only reads
 * it, and works out the figures each rule is called on from the scorecards' counts.
 */
import type { GateVerdict, Rule } from "@/contracts/gateVerdict";
import type { Ratio, Scorecard } from "@/contracts/scorecard";

/** What the API answers: production and the candidate on the smoke subset, the template over the
 * full benchmark, and the gate's verdict on the candidate. */
export interface ProvingGround {
  readonly baseline: Scorecard;
  readonly candidate: Scorecard;
  readonly benchmark: Scorecard;
  readonly verdict: GateVerdict;
}

const RULES: readonly Rule[] = [
  "unsupported_claims",
  "policy_violations",
  "verifier_catch",
  "corrections_carried",
  "storyline_recall",
  "model_written",
  "latency_p95",
];
const RATIOS = [
  "supportedClaims",
  "storylineRecall",
  "keyMomentPrecision",
  "verifierCatch",
  "modelWritten",
  "firstAttemptPass",
  "correctionsCarried",
] as const;
const PERCENT = 100;
const MS_PER_SECOND = 1000;

type Fields = Record<string, unknown>;
const isObject = (v: unknown): v is Fields =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isCount = (v: unknown): v is number => Number.isInteger(v) && (v as number) >= 0;
const isString = (v: unknown): v is string => typeof v === "string";

function isRatio(v: unknown): boolean {
  return isObject(v) && isCount(v.hit) && isCount(v.of) && (v.hit as number) <= (v.of as number);
}

function isScorecard(v: unknown): v is Scorecard {
  if (!isObject(v) || !isObject(v.configuration) || !isObject(v.metrics)) return false;
  const { configuration: c, metrics: m } = v;
  const latency = m.latencyMs;
  return (
    isString(c.name) &&
    isString(c.analystPrompt) &&
    isCount(v.matches) &&
    isString(v.firstMatch) &&
    Array.isArray(v.failures) &&
    RATIOS.every((key) => isRatio(m[key])) &&
    isCount(m.policyViolations) &&
    (latency === null ||
      (isObject(latency) && typeof latency.p50 === "number" && typeof latency.p95 === "number")) &&
    (m.costUsd === null || typeof m.costUsd === "number")
  );
}

function isVerdict(v: unknown): v is GateVerdict {
  return (
    isObject(v) &&
    typeof v.allowed === "boolean" &&
    Array.isArray(v.checks) &&
    v.checks.length > 0 &&
    v.checks.every(
      (c) =>
        isObject(c) &&
        (RULES as readonly unknown[]).includes(c.rule) &&
        typeof c.passed === "boolean" &&
        isString(c.detail),
    )
  );
}

/** The API's answer if it is shaped as one; nothing otherwise. */
export function parseProvingGround(value: unknown): ProvingGround | null {
  if (!isObject(value)) return null;
  const { baseline, candidate, benchmark, verdict } = value;
  if (![baseline, candidate, benchmark].every(isScorecard) || !isVerdict(verdict)) return null;
  return value as unknown as ProvingGround;
}

const rate = (r: Ratio): number => (r.of ? r.hit / r.of : 1);
const percent = (r: Ratio): string => `${(rate(r) * PERCENT).toFixed(1)}%`;
const counted = (r: Ratio): string => `${r.hit} of ${r.of}`;
const seconds = (ms: number): string => `${(ms / MS_PER_SECOND).toFixed(1)} s`;
const unsupported = (r: Ratio): string => `${r.of - r.hit} of ${r.of}`;

/** "Analyst prompt v1.4" from `analyst/v1.4`; the template is the template. */
export function promptName(card: Scorecard): string {
  const prompt = card.configuration.analystPrompt;
  return prompt === "template"
    ? "the template"
    : `Analyst prompt ${prompt.split("/")[1] ?? prompt}`;
}

/** One rule of the gate, called on the candidate's figure against production's. */
export interface Station {
  readonly rule: Rule;
  readonly title: string;
  readonly go: boolean;
  readonly candidate: string;
  readonly baseline: string;
  readonly allowance: string;
  readonly detail: string;
}

interface RuleText {
  readonly title: string;
  readonly allowance: string;
  readonly figure: (card: Scorecard) => string;
}

const TEXT: Readonly<Record<Rule, RuleText>> = {
  unsupported_claims: {
    title: "Nothing untrue on air",
    allowance: "None allowed",
    figure: (c) => unsupported(c.metrics.supportedClaims),
  },
  policy_violations: {
    title: "Every partner's policy kept",
    allowance: "None allowed",
    figure: (c) => `${c.metrics.policyViolations} breaches`,
  },
  verifier_catch: {
    title: "Every planted lie refused",
    allowance: "Every one",
    figure: (c) => counted(c.metrics.verifierCatch),
  },
  corrections_carried: {
    title: "Every correction carried",
    allowance: "Every one",
    figure: (c) => counted(c.metrics.correctionsCarried),
  },
  storyline_recall: {
    title: "Planted stories found",
    allowance: "May drop 3 points",
    figure: (c) => percent(c.metrics.storylineRecall),
  },
  model_written: {
    title: "Written by the model",
    allowance: "May drop 5 points",
    figure: (c) => percent(c.metrics.modelWritten),
  },
  latency_p95: {
    title: "Time to explain a moment",
    allowance: "May grow 15%",
    figure: (c) => (c.metrics.latencyMs ? seconds(c.metrics.latencyMs.p95) : "not measured"),
  },
};

/** The poll: every rule the gate checked, in its order, called go or no-go. */
export function poll(ground: ProvingGround): Station[] {
  return ground.verdict.checks.map((check) => {
    const text = TEXT[check.rule];
    return {
      rule: check.rule,
      title: text.title,
      go: check.passed,
      candidate: text.figure(ground.candidate),
      baseline: text.figure(ground.baseline),
      allowance: text.allowance,
      detail: check.detail,
    };
  });
}

export interface VerdictLine {
  readonly tone: "green" | "red";
  readonly text: string;
}

/** The one line read first: what the gate decided, on what, and how many rules said no. */
export function verdictLine(ground: ProvingGround): VerdictLine {
  const { checks, allowed } = ground.verdict;
  const noGo = checks.filter((c) => !c.passed).length;
  const against = `against production (${ground.baseline.configuration.analystPrompt.split("/")[1] ?? "?"})`;
  const subject = promptName(ground.candidate);
  return allowed
    ? {
        tone: "green",
        text: `The Release Gate allows ${subject}: all ${checks.length} rules call go ${against}.`,
      }
    : {
        tone: "red",
        text: `The Release Gate blocks ${subject}: ${noGo} of ${checks.length} rules call no-go ${against}.`,
      };
}

/** A measure in both runs, and whether the gate rules on it or only reports it. */
export interface Measure {
  readonly label: string;
  readonly baseline: string;
  readonly candidate: string;
  readonly gated: boolean;
}

const both = (r: Ratio): string => `${counted(r)} (${percent(r)})`;
const latencyOf = (card: Scorecard, at: "p50" | "p95"): string =>
  card.metrics.latencyMs ? seconds(card.metrics.latencyMs[at]) : "not measured";
const costOf = (card: Scorecard): string =>
  card.metrics.costUsd === null ? "none" : `$${card.metrics.costUsd.toFixed(2)}`;

const MEASURES: readonly (readonly [string, boolean, (c: Scorecard) => string])[] = [
  ["Unsupported claims on air", true, (c) => unsupported(c.metrics.supportedClaims)],
  ["Planted stories found", true, (c) => both(c.metrics.storylineRecall)],
  ["About a real moment", false, (c) => both(c.metrics.keyMomentPrecision)],
  ["Planted lies refused", true, (c) => counted(c.metrics.verifierCatch)],
  ["Corrections carried", true, (c) => counted(c.metrics.correctionsCarried)],
  ["Policy breaches", true, (c) => String(c.metrics.policyViolations)],
  ["Written by the model", true, (c) => both(c.metrics.modelWritten)],
  ["Passed first time", false, (c) => both(c.metrics.firstAttemptPass)],
  ["Time to explain (p50)", false, (c) => latencyOf(c, "p50")],
  ["Time to explain (p95)", true, (c) => latencyOf(c, "p95")],
  ["Cost of the run", false, costOf],
];

/** Every measure, production beside the candidate. */
export function measures(ground: ProvingGround): Measure[] {
  return MEASURES.map(([label, gated, figure]) => ({
    label,
    baseline: figure(ground.baseline),
    candidate: figure(ground.candidate),
    gated,
  }));
}
