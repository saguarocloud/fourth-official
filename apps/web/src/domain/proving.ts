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

// `analyst/v1.2`, or `template` for a run without a model.
const PROMPT = /^(template|[a-z][a-z-]{1,31}\/v[0-9]{1,3}\.[0-9]{1,3})$/;
const isStrings = (v: unknown): v is string[] => Array.isArray(v) && v.every(isString);

function isFailure(v: unknown): boolean {
  return (
    isObject(v) &&
    ["matchId", "itemId", "claimId", "text"].every((key) => isString(v[key])) &&
    isStrings(v.eventIds) &&
    isStrings(v.reasons) &&
    v.reasons.length > 0
  );
}

function isScorecard(v: unknown): v is Scorecard {
  if (!isObject(v) || !isObject(v.configuration) || !isObject(v.metrics)) return false;
  const { configuration: c, metrics: m } = v;
  const latency = m.latencyMs;
  return (
    isString(c.name) &&
    isString(c.analystPrompt) &&
    PROMPT.test(c.analystPrompt) &&
    isStrings(c.models) &&
    isCount(v.matches) &&
    isString(v.firstMatch) &&
    isString(v.generatedAt) &&
    Array.isArray(v.failures) &&
    v.failures.every(isFailure) &&
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
  // The gate compares runs over the same benchmark only; anything else is not its verdict.
  const [b, c] = [baseline as Scorecard, candidate as Scorecard];
  if (b.matches !== c.matches || b.firstMatch !== c.firstMatch) return null;
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
}

const latencyOf = (card: Scorecard, at: "p50" | "p95"): string =>
  card.metrics.latencyMs ? seconds(card.metrics.latencyMs[at]) : "not measured";
const costOf = (card: Scorecard): string =>
  card.metrics.costUsd === null ? "none" : `$${card.metrics.costUsd.toFixed(2)}`;

interface RuleText {
  // One name per measure, the same in the poll, the table and the benchmark.
  readonly title: string;
  // What the rule allows, as the gate applies it.
  readonly rule: string;
  readonly figure: (card: Scorecard) => string;
}

const RULE_TEXT: Readonly<Record<Rule, RuleText>> = {
  unsupported_claims: {
    title: "Unsupported claims on air",
    rule: "none",
    figure: (c) => unsupported(c.metrics.supportedClaims),
  },
  policy_violations: {
    title: "Policy breaches",
    rule: "none",
    figure: (c) => String(c.metrics.policyViolations),
  },
  verifier_catch: {
    title: "Planted lies refused",
    rule: "every one",
    figure: (c) => counted(c.metrics.verifierCatch),
  },
  corrections_carried: {
    title: "Corrections carried",
    rule: "every one",
    figure: (c) => counted(c.metrics.correctionsCarried),
  },
  storyline_recall: {
    title: "Planted stories found",
    rule: "may drop 3 points",
    figure: (c) => percent(c.metrics.storylineRecall),
  },
  model_written: {
    title: "Written by the model",
    rule: "may drop 5 points",
    figure: (c) => percent(c.metrics.modelWritten),
  },
  latency_p95: {
    title: "Time to explain (p95)",
    rule: "may grow 15%",
    figure: (c) => latencyOf(c, "p95"),
  },
};

/** The poll: every rule the gate checked, in its order, called go or no-go. */
export function poll(ground: ProvingGround): Station[] {
  return ground.verdict.checks.map((check) => {
    const text = RULE_TEXT[check.rule];
    return {
      rule: check.rule,
      title: text.title,
      go: check.passed,
      candidate: text.figure(ground.candidate),
      baseline: text.figure(ground.baseline),
      allowance: `Rule: ${text.rule}`,
    };
  });
}

export interface VerdictLine {
  readonly tone: "green" | "red";
  readonly text: string;
}

const lowerFirst = (text: string): string => text.charAt(0).toLowerCase() + text.slice(1);

/** The one line read first: what the gate decided, and, when it blocks, which rules said no and
 * by how much. */
export function verdictLine(ground: ProvingGround): VerdictLine {
  const subject = `${promptName(ground.candidate)} against production's ${
    ground.baseline.configuration.analystPrompt.split("/")[1] ?? "configuration"
  }`;
  const total = ground.verdict.checks.length;
  if (ground.verdict.allowed) {
    return {
      tone: "green",
      text: `The Release Gate allows ${subject}: all ${total} rules call go.`,
    };
  }
  const noGo = poll(ground).filter((s) => !s.go);
  const why = noGo.map(
    (s) =>
      `${lowerFirst(s.title)}, ${s.candidate} against ${s.baseline} (${RULE_TEXT[s.rule].rule})`,
  );
  return {
    tone: "red",
    text: `The Release Gate blocks ${subject} on ${noGo.length} of ${total} rules: ${why.join("; ")}.`,
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
// The gated measures read as counts with their rate where a rule is on the rate.
const TABLE_FIGURE: Readonly<Partial<Record<Rule, (c: Scorecard) => string>>> = {
  storyline_recall: (c) => both(c.metrics.storylineRecall),
  model_written: (c) => both(c.metrics.modelWritten),
};
const REPORTED: readonly (readonly [string, (c: Scorecard) => string])[] = [
  ["About a real moment", (c) => both(c.metrics.keyMomentPrecision)],
  ["Passed first time", (c) => both(c.metrics.firstAttemptPass)],
  ["Time to explain (p50)", (c) => latencyOf(c, "p50")],
  ["Cost of the run", costOf],
];

/** Every measure, production beside the candidate: the gated ones in the poll's order, then
 * those only reported. */
export function measures(ground: ProvingGround): Measure[] {
  const gated = RULES.map((rule) => {
    const figure = TABLE_FIGURE[rule] ?? RULE_TEXT[rule].figure;
    return {
      label: RULE_TEXT[rule].title,
      baseline: figure(ground.baseline),
      candidate: figure(ground.candidate),
      gated: true,
    };
  });
  const reported = REPORTED.map(([label, figure]) => ({
    label,
    baseline: figure(ground.baseline),
    candidate: figure(ground.candidate),
    gated: false,
  }));
  return [...gated, ...reported];
}
