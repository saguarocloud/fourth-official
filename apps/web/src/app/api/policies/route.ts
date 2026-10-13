import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";
import { NO_STORE } from "@/lib/studioRequest";

/** Every partner's current policy, from the match API (ADR-015). */
export async function GET(): Promise<Response> {
  try {
    const upstream = await fetch(`${apiBase()}/api/policies`, {
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    if (!upstream.ok) throw new Error(`match API answered ${upstream.status}`);
    return Response.json(await upstream.json(), { headers: NO_STORE });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
}
