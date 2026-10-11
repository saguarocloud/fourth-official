import { connection } from "next/server";

import { apiBase, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";

const NO_STORE = { "Cache-Control": "no-store" };

/** The broadcast partners: language, disclosure, which items wait for an editor, and who
 * decides on them. */
export async function GET(): Promise<Response> {
  await connection();
  try {
    const upstream = await fetch(`${apiBase()}/api/tenants`, {
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
