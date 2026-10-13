/**
 * Policy Studio: a partner's policy history as the API serves it (ADR-015), read as a ledger of
 * versions, each with what it changed in plain words, and written back as YAML for the raw view.
 */
import type { PolicyChange, PolicyHistory, TenantPolicy } from "@/contracts/policyHistory";

type Fields = Record<string, unknown>;
const isObject = (v: unknown): v is Fields =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isString = (v: unknown): v is string => typeof v === "string";
const isStrings = (v: unknown): v is string[] => Array.isArray(v) && v.every(isString);

const ACTIONS = ["bundled", "edited", "reset"] as const;
const LISTS = [
  "tone",
  "preferTerms",
  "avoidTerms",
  "blockedTopics",
  "approvalRequired",
  "templates",
];
const TEXTS = [
  "tenantId",
  "displayName",
  "locale",
  "disclosureMode",
  "correctionBehaviour",
  "dutyEditor",
];
const NUMBERS = ["version", "latencyBudgetMs", "maxItemsPerMinute"];

function isPolicy(v: unknown): v is TenantPolicy {
  return (
    isObject(v) &&
    LISTS.every((key) => isStrings(v[key])) &&
    TEXTS.every((key) => isString(v[key])) &&
    NUMBERS.every((key) => Number.isInteger(v[key]))
  );
}

function isChange(v: unknown): v is PolicyChange {
  return (
    isObject(v) &&
    Number.isInteger(v.version) &&
    (ACTIONS as readonly unknown[]).includes(v.action) &&
    ["tenantId", "editor", "changedAt", "reason"].every((key) => isString(v[key])) &&
    isStrings(v.fields)
  );
}

/** The API's history if it is shaped as one: every version with the change that made it. */
export function parseHistory(value: unknown): PolicyHistory | null {
  if (!isObject(value) || !isString(value.tenantId)) return null;
  const { versions, changes } = value;
  if (!Array.isArray(versions) || !Array.isArray(changes) || versions.length === 0) return null;
  if (versions.length !== changes.length) return null;
  if (!versions.every(isPolicy) || !changes.every(isChange)) return null;
  const aligned = versions.every((v, i) => v.version === (changes[i] as PolicyChange).version);
  return aligned ? (value as unknown as PolicyHistory) : null;
}

type EditableField = Exclude<keyof TenantPolicy, "tenantId" | "version" | "locale" | "dutyEditor">;

const TOPICS: Readonly<Record<string, string>> = {
  injury_speculation: "Injury speculation",
  betting: "Betting",
  transfer_rumour: "Transfer rumours",
  referee_criticism: "Criticism of referees",
  off_field: "Off the field",
};
const KINDS: Readonly<Record<string, string>> = {
  insight: "Insights",
  recap: "Recaps",
  stat: "Stat cards",
  correction: "Corrections",
  score: "Score bugs",
};
const TEMPLATES: Readonly<Record<string, string>> = {
  lower_third: "Lower third",
  stat_card: "Stat card",
  correction_strap: "Correction strap",
  score_bug: "Score bug",
};
const DISCLOSURE: Readonly<Record<string, string>> = {
  "label-all": "Label every AI item",
  "label-unless-approved": "Label unless an editor approved it",
  "eu-strict": "EU strict: label every AI item, name the editor",
};
const CORRECTIONS: Readonly<Record<string, string>> = {
  "auto-amend": "Amend automatically",
  "retract-and-notify": "Pull and notify",
  escalate: "Hold the new version for an editor",
};

const named = (names: Readonly<Record<string, string>>) => (value: unknown) =>
  isStrings(value)
    ? value.length === 0
      ? "None"
      : value.map((v) => names[v] ?? v).join(", ")
    : (names[String(value)] ?? String(value));
const words = (value: unknown) =>
  isStrings(value) ? (value.length === 0 ? "None" : value.join(", ")) : String(value);

/** A field Policy Studio may change, how it is labelled and how its value reads. */
export interface FieldInfo {
  readonly field: EditableField;
  readonly label: string;
  readonly read: (value: unknown) => string;
}

/** The fields a studio editor may change, in the order a policy lists them. Who the policy
 * belongs to (the partner, its locale, its duty editor) is not among them. */
export const EDITABLE_FIELDS: readonly FieldInfo[] = [
  { field: "displayName", label: "Name on air", read: words },
  { field: "tone", label: "Tone", read: words },
  { field: "preferTerms", label: "Preferred terms", read: words },
  { field: "avoidTerms", label: "Avoided terms", read: words },
  { field: "blockedTopics", label: "Blocked topics", read: named(TOPICS) },
  { field: "approvalRequired", label: "Held for the duty editor", read: named(KINDS) },
  { field: "disclosureMode", label: "AI disclosure", read: named(DISCLOSURE) },
  { field: "latencyBudgetMs", label: "Latency budget", read: (v) => `${Number(v) / 1000} s` },
  { field: "maxItemsPerMinute", label: "Items a minute", read: (v) => String(v) },
  { field: "templates", label: "Graphics allowed", read: named(TEMPLATES) },
  { field: "correctionBehaviour", label: "When a correction arrives", read: named(CORRECTIONS) },
];

export const LABELS = { TOPICS, KINDS, TEMPLATES, DISCLOSURE, CORRECTIONS } as const;

/** One field a version changed, read before and after. */
export interface FieldChange {
  readonly field: EditableField;
  readonly label: string;
  readonly before: string;
  readonly after: string;
}

/** What `after` changed from `before`, field by field, in plain words. */
export function changesOf(before: TenantPolicy, after: TenantPolicy): FieldChange[] {
  return EDITABLE_FIELDS.filter(
    ({ field }) => JSON.stringify(before[field]) !== JSON.stringify(after[field]),
  ).map(({ field, label, read }) => ({
    field,
    label,
    before: read(before[field]),
    after: read(after[field]),
  }));
}

const ACTION_WORDS: Readonly<Record<PolicyChange["action"], string>> = {
  bundled: "Shipped",
  edited: "Edited",
  reset: "Reset",
};

/** The ledger's line for a change: who, when, and why. */
export function versionLine(change: PolicyChange): string {
  if (change.action === "bundled") return "Shipped with the release";
  const at = change.changedAt.slice(11, 16);
  return `${ACTION_WORDS[change.action]} by ${change.editor} at ${at} UTC: “${change.reason}”`;
}

// The order a policy file lists its fields in.
const ORDER: readonly (keyof TenantPolicy)[] = [
  "tenantId",
  "version",
  "displayName",
  "locale",
  "tone",
  "preferTerms",
  "avoidTerms",
  "blockedTopics",
  "approvalRequired",
  "disclosureMode",
  "latencyBudgetMs",
  "maxItemsPerMinute",
  "templates",
  "correctionBehaviour",
  "dutyEditor",
];

// Every string double-quoted (JSON's quoting is valid YAML): a term can never break a line,
// open a mapping or turn into another type.
const scalar = (value: unknown): string =>
  typeof value === "number" ? String(value) : JSON.stringify(String(value));

/** The policy as YAML for the raw view, read back by the API's strict loader as it was. */
export function toYaml(policy: TenantPolicy): string {
  return (
    ORDER.map((key) => {
      const value = policy[key];
      return Array.isArray(value)
        ? `${key}: [${value.map(scalar).join(", ")}]`
        : `${key}: ${scalar(value)}`;
    }).join("\n") + "\n"
  );
}
