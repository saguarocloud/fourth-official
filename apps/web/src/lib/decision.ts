/**
 * An editor's decision as the studio sends it, checked before it leaves the browser and again in
 * the proxy: the same rules the API and the contract hold (ADR-011).
 */

export interface DecisionBody {
  readonly decision: "approved" | "rejected";
  /** The run the editor saw, so a page left open across a replay cannot decide the new run. */
  readonly generation: number;
  readonly reason?: string;
}

export const REASON_MAX = 200;
/** Control, format, separator, private-use and unassigned characters: never in a one-line reason. */
const NOT_ONE_LINE = /[\p{Cc}\p{Cf}\p{Cs}\p{Co}\p{Cn}\p{Zl}\p{Zp}]/u;
const KEYS = new Set(["decision", "generation", "reason"]);

/** A reason the contract accepts: one line of 1 to 200 characters, trimmed; null otherwise. */
export function cleanReason(text: string): string | null {
  const trimmed = text.trim();
  if (trimmed.length === 0 || trimmed.length > REASON_MAX || NOT_ONE_LINE.test(trimmed)) {
    return null;
  }
  return trimmed;
}

/** The decision in `value`, or null when it is not one the API would accept. */
export function parseDecision(value: unknown): DecisionBody | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const body = value as Record<string, unknown>;
  if (Object.keys(body).some((key) => !KEYS.has(key))) return null;
  const { decision, generation, reason } = body;
  if (decision !== "approved" && decision !== "rejected") return null;
  if (typeof generation !== "number" || !Number.isInteger(generation) || generation < 0) {
    return null;
  }
  if (decision === "approved") return reason === undefined ? { decision, generation } : null;
  const clean = typeof reason === "string" ? cleanReason(reason) : null;
  return clean === null ? null : { decision, generation, reason: clean };
}
