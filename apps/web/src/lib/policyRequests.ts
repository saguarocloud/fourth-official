/** What the studio may send Policy Studio's API: checked here so nothing else reaches it. */

export const TENANTS = new Set(["northlight-sport", "tribuna-austral", "rheinblick-sport"]);
// A policy's YAML is at most 64 KB; the rest of an edit is small.
export const MAX_EDIT_BYTES = 80 * 1024;
const MAX_REASON = 200;

type Fields = Record<string, unknown>;
const isObject = (v: unknown): v is Fields =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isReason = (v: unknown): v is string =>
  typeof v === "string" && v.trim().length > 0 && v.length <= MAX_REASON && !/[\n\r]/.test(v);

export interface Edit {
  readonly policy?: Fields;
  readonly yaml?: string;
  readonly baseVersion: number;
  readonly reason: string;
}

/** An edit as the API takes it, or null: fields from the form or YAML, never both. */
export function parseEdit(value: unknown): Edit | null {
  if (!isObject(value)) return null;
  const allowed = new Set(["policy", "yaml", "baseVersion", "reason"]);
  if (Object.keys(value).some((key) => !allowed.has(key))) return null;
  const { policy, yaml, baseVersion, reason } = value;
  if (!Number.isInteger(baseVersion) || (baseVersion as number) < 1 || !isReason(reason)) {
    return null;
  }
  if (isObject(policy) && yaml === undefined) {
    return { policy, baseVersion: baseVersion as number, reason };
  }
  if (typeof yaml === "string" && policy === undefined) {
    return { yaml, baseVersion: baseVersion as number, reason };
  }
  return null;
}

/** A reset as the API takes it, or null. */
export function parseReset(value: unknown): { readonly reason: string } | null {
  if (!isObject(value) || Object.keys(value).length !== 1 || !isReason(value.reason)) return null;
  return { reason: value.reason };
}
