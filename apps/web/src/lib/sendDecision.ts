import type { DecisionBody } from "./decision";

export interface DecisionTarget {
  readonly tenantId: string;
  readonly matchId: string;
  readonly itemId: string;
}

export type DecisionOutcome =
  { readonly ok: true } | { readonly ok: false; readonly message: string };

const UNAVAILABLE = "The match service is unavailable. Try again shortly.";
const FIXED: Readonly<Record<number, string>> = {
  404: "That item is no longer on the feed. Reload to see the current run.",
  422: "That decision could not be sent. Check the reason and try again.",
};
// The API's own reasons for these, which are written to be shown.
const EXPLAINED = new Set([409, 410, 503]);

function sentence(detail: string): string {
  const text = detail.trim();
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}${/[.!?]$/.test(text) ? "" : "."}`;
}

async function messageOf(response: Response): Promise<string> {
  if (EXPLAINED.has(response.status)) {
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.length > 0) return sentence(body.detail);
  }
  return FIXED[response.status] ?? UNAVAILABLE;
}

/** Send an editor's decision through this app's own route (ADR-011). */
export async function sendDecision(
  target: DecisionTarget,
  body: DecisionBody,
): Promise<DecisionOutcome> {
  const { tenantId, matchId, itemId } = target;
  try {
    const response = await fetch(
      `/api/tenants/${encodeURIComponent(tenantId)}/matches/${encodeURIComponent(matchId)}/items/${encodeURIComponent(itemId)}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-By": "fourth-official" },
        body: JSON.stringify(body),
        cache: "no-store",
      },
    );
    return response.ok ? { ok: true } : { ok: false, message: await messageOf(response) };
  } catch {
    return { ok: false, message: UNAVAILABLE };
  }
}
