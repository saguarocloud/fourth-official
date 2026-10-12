/**
 * Provenance: an item's signed record, as the match API answers for it (ADR-013), read as the
 * item's life. The API checks the signature; this module reads what it said and refuses an answer
 * that is not shaped as a record, so a broken one fails loudly instead of rendering half a story.
 */
import type {
  Algorithm,
  Provenance,
  ProvenanceRecord,
  SignedProvenance,
  State,
} from "@/contracts/provenance";

import type { TenantItemEntry } from "@/contracts/feed";
import { plural } from "@/lib/plural";

import { latestVersions } from "./approvals";
import type { BroadcastState } from "./broadcast";

export interface Verification {
  readonly valid: boolean;
  readonly reason: string | null;
}

/** What the API answers for an item: its record, if it reads, and whether the record holds. */
export interface ProvenanceAnswer {
  readonly provenance: SignedProvenance | null;
  readonly verification: Verification;
}

const ALGORITHMS: readonly Algorithm[] = ["ES256", "HS256"];
const STATES: readonly State[] = ["on_air", "pending_approval", "rejected", "retracted", "amended"];

type Fields = Record<string, unknown>;

// The API writes times as ISO 8601 in UTC, to the millisecond; the time of day is read from them.
const UTC_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$/;

const isObject = (value: unknown): value is Fields =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isString = (value: unknown): value is string => typeof value === "string";
const isStrings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every(isString);
const isTime = (value: unknown): value is string => isString(value) && UTC_TIME.test(value);
const isOneOf = <T extends string>(value: unknown, allowed: readonly T[]): value is T =>
  isString(value) && (allowed as readonly string[]).includes(value);

function isAuthor(value: unknown): value is Provenance {
  return (
    isObject(value) &&
    isString(value.agent) &&
    isString(value.model) &&
    isOneOf(value.producedBy, ["model", "template"] as const) &&
    isString(value.promptVersion)
  );
}

function isClaim(value: unknown): boolean {
  return (
    isObject(value) &&
    isString(value.text) &&
    isObject(value.evidence) &&
    isStrings(value.evidence.eventIds) &&
    isStrings(value.evidence.metricSnapshotIds)
  );
}

function isAttempt(value: unknown): boolean {
  return (
    isObject(value) &&
    isString(value.agent) &&
    isString(value.model) &&
    Number.isInteger(value.number) &&
    isOneOf(value.outcome, ["passed", "failed", "error"] as const) &&
    isStrings(value.findings)
  );
}

// A rejection always carries its reason; an approval never does (ADR-011).
function isApproval(value: unknown): boolean {
  if (!isObject(value) || !isString(value.editor) || !isTime(value.decidedAt)) return false;
  if (value.decision === "rejected") return isString(value.reason);
  return value.decision === "approved" && (value.reason === undefined || value.reason === null);
}

function isDisclosure(value: unknown): boolean {
  return (
    isObject(value) &&
    (value.label === null || isString(value.label)) &&
    isString(value.mode) &&
    isString(value.reason)
  );
}

function isRecord(value: unknown): value is ProvenanceRecord {
  if (!isObject(value)) return false;
  const { claims, attempts } = value;
  return (
    ["itemId", "insightId", "matchId", "tenantId", "locale", "headline", "issuer"].every((key) =>
      isString(value[key]),
    ) &&
    isTime(value.issuedAt) &&
    isOneOf(value.state, STATES) &&
    Number.isInteger(value.version) &&
    Number.isInteger(value.feedEntry) &&
    (value.supersedes === null || isString(value.supersedes)) &&
    Array.isArray(claims) &&
    claims.length > 0 &&
    claims.every(isClaim) &&
    Array.isArray(attempts) &&
    attempts.every(isAttempt) &&
    isStrings(value.corrections) &&
    isAuthor(value.localized) &&
    (value.canonical === null || isAuthor(value.canonical)) &&
    (value.approval === null || isApproval(value.approval)) &&
    (value.disclosure === null || isDisclosure(value.disclosure))
  );
}

function isSigned(value: unknown): value is SignedProvenance {
  return (
    isObject(value) &&
    isOneOf(value.algorithm, ALGORITHMS) &&
    isString(value.contentHash) &&
    isString(value.keyId) &&
    isString(value.signature) &&
    isRecord(value.record)
  );
}

/** The API's answer if it is shaped as one; nothing otherwise. */
export function parseAnswer(value: unknown): ProvenanceAnswer | null {
  if (!isObject(value) || !isObject(value.verification)) return null;
  const { valid, reason } = value.verification;
  if (typeof valid !== "boolean" || !(reason === null || isString(reason))) return null;
  // A verdict of valid with no record behind it is no answer: nothing was verified.
  if (value.provenance === null ? valid : !isSigned(value.provenance)) return null;
  return value as unknown as ProvenanceAnswer;
}

/** Who wrote a text: a model, named with its agent and prompt, or code. */
export function authorOf(author: Provenance): string {
  return author.producedBy === "template"
    ? "A template, in code"
    : `${author.model}, as the ${author.agent} agent, prompt ${author.promptVersion}`;
}

/** Verified under the studio's key; intact but signed by a development key; or not verified. */
export type SealTone = "verified" | "development" | "failed";

export interface Seal {
  readonly tone: SealTone;
  readonly title: string;
  readonly detail: string | null;
}

/** The verdict at the top of a record. Only the studio's production key (ES256) earns the green
 * seal: a local HMAC key proves nothing to anyone outside the studio. */
export function sealOf(answer: ProvenanceAnswer): Seal {
  if (!answer.verification.valid) {
    return {
      tone: "failed",
      title: "Does not verify",
      detail: answer.verification.reason ?? "The record could not be checked.",
    };
  }
  return answer.provenance?.algorithm === "ES256"
    ? { tone: "verified", title: "Signed and unchanged", detail: null }
    : {
        tone: "development",
        title: "Unchanged, signed with a development key",
        detail: "The signature holds, but a local key signed it, not the studio's production key.",
      };
}

/** Which key signed a record. HS256 is only ever a local key, for development and tests. */
export function signerOf(signed: SignedProvenance): string {
  return signed.algorithm === "ES256"
    ? "The studio's key in Azure Key Vault (ES256)"
    : "A local development key (HS256)";
}

/** A step's lamp, in the state vocabulary: a plain step is unlit; where the item ended is lit in
 * that state's colour. */
export type StepTone = "step" | "aired" | "held" | "dropped" | "retracted" | "amended";

/** One moment in an item's life, as its record tells it. */
export interface LifeStep {
  readonly label: string;
  readonly detail: string;
  readonly tone: StepTone;
}

const lowerFirst = (text: string): string => text.charAt(0).toLowerCase() + text.slice(1);
// Decisions are recorded in UTC; the time is read from the record as written, never computed.
const utcTime = (iso: string): string => `${iso.slice(11, 19)} UTC`;

function byCorrections(ids: readonly string[]): string {
  return ids.length === 0
    ? "a correction"
    : `${ids.length === 1 ? "correction" : "corrections"} ${ids.join(", ")}`;
}

function checked(record: ProvenanceRecord): LifeStep {
  const { attempts } = record;
  const refused = [...new Set(attempts.flatMap((a) => (a.outcome === "passed" ? [] : a.findings)))];
  const passed = attempts.findLast((a) => a.outcome === "passed");
  const detail = passed
    ? `Passed the verifier on attempt ${passed.number} of ${attempts.length}`
    : `Checked in ${plural(attempts.length, "attempt", "attempts")}`;
  return {
    label: "Checked",
    detail: refused.length > 0 ? `${detail}; refused before: ${refused.join(", ")}` : detail,
    tone: "step",
  };
}

function decided(record: ProvenanceRecord): LifeStep[] {
  const { approval } = record;
  if (approval === null) return [];
  const by = `By ${approval.editor} at ${utcTime(approval.decidedAt)}`;
  return approval.decision === "approved"
    ? [{ label: "Approved", detail: by, tone: "step" }]
    : [{ label: "Rejected", detail: `${by}: “${approval.reason ?? ""}”`, tone: "dropped" }];
}

function ending(record: ProvenanceRecord): LifeStep {
  switch (record.state) {
    case "on_air":
      return {
        label: "On air",
        detail: record.approval ? "Aired as approved" : "Aired under the partner's policy",
        tone: "aired",
      };
    case "pending_approval":
      return {
        label: "Held",
        detail: "Off air until the partner's duty editor decides",
        tone: "held",
      };
    case "rejected":
      return { label: "Kept off air", detail: "Never aired", tone: "dropped" };
    case "retracted":
      return {
        label: "Pulled",
        detail: `Pulled by ${byCorrections(record.corrections)}`,
        tone: "retracted",
      };
    case "amended":
      return {
        label: "Replaced",
        detail: `Superseded by a corrected version after ${byCorrections(record.corrections)}`,
        tone: "amended",
      };
  }
}

/** The item's life, oldest first: who wrote it, how it was checked and localised, who decided,
 * and where it ended. */
export function lifeOf(record: ProvenanceRecord): LifeStep[] {
  const author = record.canonical ?? record.localized;
  const written: LifeStep = {
    label: "Written",
    detail: `${authorOf(author)} · insight ${record.insightId}`,
    tone: "step",
  };
  const remade: LifeStep[] =
    record.supersedes === null
      ? []
      : [
          {
            label: "Remade",
            detail: `Version ${record.version}, replacing ${record.supersedes} after a correction`,
            tone: "step",
          },
        ];
  const localised: LifeStep = {
    label: "Localised",
    detail: `${record.locale}, by ${lowerFirst(authorOf(record.localized))}`,
    tone: "step",
  };
  return [written, ...remade, checked(record), localised, ...decided(record), ending(record)];
}

/** The partner items with a record to read: every narrative item once, as its latest version,
 * newest first. Score bugs carry no claims, so they have none. */
export function itemsOnRecord(state: BroadcastState): TenantItemEntry[] {
  return latestVersions(state)
    .filter((item) => item.localized !== null)
    .sort((a, b) => b.entrySeq - a.entrySeq);
}
