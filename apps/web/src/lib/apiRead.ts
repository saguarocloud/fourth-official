import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";
import type { RateLimit } from "@/lib/rateLimit";
import { clientOf } from "@/lib/streamSlots";

export const NO_STORE = { "Cache-Control": "no-store" };

interface Read {
  /** The match API's path, such as `/api/operations`. */
  readonly path: string;
  /** Reads per visitor. */
  readonly limit: RateLimit;
  /** Headers for a good answer: how long browsers and the proxy may keep it. */
  readonly cache: Record<string, string>;
}

/** A public, read-only answer from the match API, passed through: each visitor's reads limited,
 * the API's 503 and 429 (with when to try again) passed on, anything else a gateway error. */
export async function readFromApi(
  request: Request,
  { path, limit, cache }: Read,
): Promise<Response> {
  const wait = limit.take(clientOf(request));
  if (wait > 0) {
    return Response.json(
      { detail: "Too many reads from here. Wait a moment and try again." },
      { status: 429, headers: { ...NO_STORE, "Retry-After": String(wait) } },
    );
  }
  try {
    const upstream = await fetch(`${apiBase()}${path}`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    if (upstream.status === 503 || upstream.status === 429) {
      const retry = upstream.headers.get("retry-after");
      return Response.json(await upstream.json(), {
        status: upstream.status,
        headers: retry ? { ...NO_STORE, "Retry-After": retry } : NO_STORE,
      });
    }
    if (upstream.status !== 200) throw new Error(`match API answered ${upstream.status}`);
    return Response.json(await upstream.json(), { headers: cache });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
}
