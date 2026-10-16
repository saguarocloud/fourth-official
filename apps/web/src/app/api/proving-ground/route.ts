import { readFromApi } from "@/lib/apiRead";
import { rateLimit } from "@/lib/rateLimit";

// The recorded runs change only with a release.
const CACHED = { "Cache-Control": "public, max-age=300" };
/** Reads per visitor per minute: far above a person reading, a bound on a script. */
const READS_PER_MINUTE = 60;
const limit = rateLimit({ perWindow: READS_PER_MINUTE, windowMs: 60_000 });

/** The Proving Ground's recorded runs and the Release Gate's verdict, from the match API
 * (ADR-014). Public and read-only. */
export function GET(request: Request): Promise<Response> {
  return readFromApi(request, { path: "/api/proving-ground", limit, cache: CACHED });
}
