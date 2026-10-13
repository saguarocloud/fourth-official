import { parseDecision } from "@/lib/decision";
import { apiBase, isMatchId, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";
import { rateLimit } from "@/lib/rateLimit";
import { clientOf } from "@/lib/streamSlots";
import { declaresMoreThan, fromTheStudio, jsonBody, NO_STORE, refuse } from "@/lib/studioRequest";

const TENANT_ID = /^[a-z]+(-[a-z]+)*$/;
const ITEM_ID = /^it-[a-z]+(-[a-z]+)*-[A-Za-z0-9_-]+$/;
const MAX_BODY = 1024;
/** Far above an editor's pace; a bound on a script, not on a producer. */
export const DECISIONS_PER_MINUTE = 20;
const limit = rateLimit({ perWindow: DECISIONS_PER_MINUTE, windowMs: 60_000 });
// The API's answers this route passes through as they are; anything else is a failure.
const PASSED = new Set([200, 404, 409, 410, 422, 503]);

interface Params {
  readonly tenantId: string;
  readonly matchId: string;
  readonly itemId: string;
}

/** An editor's decision on a held item, forwarded to the match API (ADR-011). */
export async function POST(
  request: Request,
  { params }: { params: Promise<Params> },
): Promise<Response> {
  if (!fromTheStudio(request)) return refuse(403, "Decisions are made from the studio.");
  if (declaresMoreThan(request, MAX_BODY)) return refuse(413, "That decision is too large.");
  const wait = limit.take(clientOf(request));
  if (wait > 0) {
    return Response.json(
      { detail: "Too many decisions from here. Wait a moment and try again." },
      { status: 429, headers: { ...NO_STORE, "Retry-After": String(wait) } },
    );
  }
  const { tenantId, matchId, itemId } = await params;
  if (
    tenantId.length > 40 ||
    !TENANT_ID.test(tenantId) ||
    !isMatchId(matchId) ||
    itemId.length > 160 ||
    !ITEM_ID.test(itemId)
  ) {
    return refuse(404, "No such item.");
  }
  const decision = parseDecision(await jsonBody(request, MAX_BODY));
  if (decision === null) return refuse(422, "That decision cannot be sent.");
  try {
    const upstream = await fetch(
      `${apiBase()}/api/tenants/${tenantId}/matches/${matchId}/items/${itemId}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-By": "fourth-official" },
        body: JSON.stringify(decision),
        cache: "no-store",
        // The studio header goes to the match API and nowhere else.
        redirect: "error",
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      },
    );
    if (!PASSED.has(upstream.status)) throw new Error(`match API answered ${upstream.status}`);
    const retry = upstream.headers.get("retry-after");
    return Response.json(await upstream.json(), {
      status: upstream.status,
      headers: retry ? { ...NO_STORE, "Retry-After": retry } : NO_STORE,
    });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
}
