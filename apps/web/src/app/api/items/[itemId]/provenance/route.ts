import { isItemId } from "@/lib/itemId";
import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";
import { rateLimit } from "@/lib/rateLimit";
import { clientOf } from "@/lib/streamSlots";

const NO_STORE = { "Cache-Control": "no-store" };
/** Reads per visitor per minute: far above a person reading records, a bound on a script. */
export const READS_PER_MINUTE = 60;
const limit = rateLimit({ perWindow: READS_PER_MINUTE, windowMs: 60_000 });
// The API's answers passed through as they are; anything else is a failure.
const PASSED = new Set([200, 404, 429, 503]);

/** An item's signed provenance record and its check, from the match API (ADR-013). Public, as
 * the Verify page is, so each visitor is limited here: the API's ingress appends this app's own
 * address, so the API sees the web app as one caller, with a higher ceiling of its own. */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ itemId: string }> },
): Promise<Response> {
  const { itemId } = await params;
  if (!isItemId(itemId)) {
    return Response.json({ detail: "No such item." }, { status: 404, headers: NO_STORE });
  }
  const wait = limit.take(clientOf(request));
  if (wait > 0) {
    return Response.json(
      { detail: "Too many reads from here. Wait a moment and try again." },
      { status: 429, headers: { ...NO_STORE, "Retry-After": String(wait) } },
    );
  }
  try {
    const upstream = await fetch(`${apiBase()}/api/items/${itemId}/provenance`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
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
