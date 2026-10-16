import { NO_STORE, readFromApi } from "@/lib/apiRead";
import { rateLimit } from "@/lib/rateLimit";

/** Reads per visitor per minute: the Control Room polls every few seconds; this bounds a script. */
const READS_PER_MINUTE = 60;
const limit = rateLimit({ perWindow: READS_PER_MINUTE, windowMs: 60_000 });

/** The Control Room's wall, computed by the API from the matchday's feeds. Public and read-only,
 * and never cached: a running match changes it by the second. */
export function GET(request: Request): Promise<Response> {
  return readFromApi(request, { path: "/api/wall", limit, cache: NO_STORE });
}
