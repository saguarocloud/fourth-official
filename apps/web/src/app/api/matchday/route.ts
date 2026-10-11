import { connection } from "next/server";

import { apiBase, sameOrigin, UNAVAILABLE, UPSTREAM_TIMEOUT_MS } from "@/lib/matchApi";

const NO_STORE = { "Cache-Control": "no-store" };

/** Whether the matchday may start now, and if not, why and from when. */
export async function GET(): Promise<Response> {
  await connection();
  try {
    const upstream = await fetch(`${apiBase()}/api/matchday`, {
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    if (!upstream.ok) throw new Error(`match API answered ${upstream.status}`);
    return Response.json(await upstream.json(), { headers: NO_STORE });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
}

/** Start the matchday replay. Only from this app's own pages: a cross-site form is refused. */
export async function POST(request: Request): Promise<Response> {
  if (!sameOrigin(request)) {
    return Response.json(
      { detail: "The matchday is started from the studio." },
      {
        status: 403,
        headers: NO_STORE,
      },
    );
  }
  try {
    const upstream = await fetch(`${apiBase()}/api/matchday`, {
      method: "POST",
      headers: { "X-Requested-By": "fourth-official" },
      cache: "no-store",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const body: unknown = await upstream.json();
    if (upstream.status >= 500) throw new Error(`match API answered ${upstream.status}`);
    return Response.json(body, { status: upstream.status, headers: NO_STORE });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502, headers: NO_STORE });
  }
}
