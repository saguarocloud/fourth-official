import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";
import { rateLimit } from "@/lib/rateLimit";
import { clientOf } from "@/lib/streamSlots";

const NO_STORE = { "Cache-Control": "no-store" };
// The recorded runs change only with a release.
const CACHED = { "Cache-Control": "public, max-age=300" };
/** Reads per visitor per minute: far above a person reading, a bound on a script. */
const READS_PER_MINUTE = 60;
const limit = rateLimit({ perWindow: READS_PER_MINUTE, windowMs: 60_000 });

/** The Proving Ground's recorded runs and the Release Gate's verdict, from the match API
 * (ADR-014). Public and read-only. */
export async function GET(request: Request): Promise<Response> {
  const wait = limit.take(clientOf(request));
  if (wait > 0) {
    return Response.json(
      { detail: "Too many reads from here. Wait a moment and try again." },
      { status: 429, headers: { ...NO_STORE, "Retry-After": String(wait) } },
    );
  }
  try {
    const upstream = await fetch(`${apiBase()}/api/proving-ground`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    if (upstream.status === 503) {
      return Response.json(await upstream.json(), { status: 503, headers: NO_STORE });
    }
    if (upstream.status !== 200) throw new Error(`match API answered ${upstream.status}`);
    return Response.json(await upstream.json(), { headers: CACHED });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
}
