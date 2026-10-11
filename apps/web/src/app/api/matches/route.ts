import { connection } from "next/server";

import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";

/** The matchday's matches and their state, from the match API. */
export async function GET(): Promise<Response> {
  await connection();
  try {
    const upstream = await fetch(`${apiBase()}/api/matches`, {
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    if (!upstream.ok) throw new Error(`match API answered ${upstream.status}`);
    return Response.json(await upstream.json(), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
