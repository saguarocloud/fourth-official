import { parseDecision } from "@/lib/decision";
import { apiBase, isMatchId, sameOrigin, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";

const NO_STORE = { "Cache-Control": "no-store" };
const TENANT_ID = /^[a-z]+(-[a-z]+)*$/;
const ITEM_ID = /^it-[a-z]+(-[a-z]+)*-[A-Za-z0-9_-]+$/;
const MAX_BODY = 1024;
// The API's answers this route passes through as they are; anything else is a failure.
const PASSED = new Set([200, 404, 409, 410, 422, 503]);

interface Params {
  readonly tenantId: string;
  readonly matchId: string;
  readonly itemId: string;
}

function refuse(status: number, detail: string): Response {
  return Response.json({ detail }, { status, headers: NO_STORE });
}

/** Only this app's own pages decide: a script on this origin that names itself and sends JSON.
 * A cross-site form can do none of that, and a cross-site fetch is refused by its own headers. */
function fromTheStudio(request: Request): boolean {
  const site = request.headers.get("sec-fetch-site");
  return (
    sameOrigin(request) &&
    (site === null || site === "same-origin") &&
    request.headers.get("x-requested-by") === "fourth-official" &&
    (request.headers.get("content-type") ?? "").split(";")[0]?.trim() === "application/json"
  );
}

async function bodyOf(request: Request): Promise<unknown> {
  const text = await request.text();
  if (text.length > MAX_BODY) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/** An editor's decision on a held item, forwarded to the match API (ADR-011). */
export async function POST(
  request: Request,
  { params }: { params: Promise<Params> },
): Promise<Response> {
  if (!fromTheStudio(request)) return refuse(403, "Decisions are made from the studio.");
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
  const decision = parseDecision(await bodyOf(request));
  if (decision === null) return refuse(422, "That decision cannot be sent.");
  try {
    const upstream = await fetch(
      `${apiBase()}/api/tenants/${tenantId}/matches/${matchId}/items/${itemId}/decision`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-By": "fourth-official" },
        body: JSON.stringify(decision),
        cache: "no-store",
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
