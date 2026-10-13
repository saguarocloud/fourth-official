import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";
import { NO_STORE, STUDIO } from "@/lib/studioRequest";

// The API's answers passed through as they are, with their reason; anything else is a failure.
const PASSED = new Set([200, 404, 409, 422, 429, 503]);

/** Send a checked edit or reset to the match API as the studio, and pass its answer on. */
export async function forward(path: string, body: unknown): Promise<Response> {
  try {
    const upstream = await fetch(`${apiBase()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-By": STUDIO },
      body: JSON.stringify(body),
      cache: "no-store",
      // The studio header goes to the match API and nowhere else.
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
