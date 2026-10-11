import { apiBase, isMatchId, UNAVAILABLE } from "@/lib/matchApi";

const STREAM_HEADERS = {
  "Content-Type": "text/event-stream",
  // no-transform: nothing between here and the browser may compress, and so buffer, the events.
  "Cache-Control": "no-cache, no-transform",
  "X-Accel-Buffering": "no",
};

/** A match's live feed as server-sent events, passed through from the match API. Closing the
 * page closes the upstream stream too. */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ matchId: string }> },
): Promise<Response> {
  const { matchId } = await params;
  if (!isMatchId(matchId)) {
    return Response.json({ detail: "unknown match" }, { status: 404 });
  }
  const lastEventId = request.headers.get("last-event-id");
  try {
    const upstream = await fetch(`${apiBase()}/api/matches/${matchId}/stream`, {
      headers: lastEventId ? { "Last-Event-ID": lastEventId } : {},
      signal: request.signal,
      cache: "no-store",
    });
    const isStream = upstream.headers.get("content-type")?.startsWith("text/event-stream");
    if (!upstream.ok || upstream.body === null || !isStream) {
      return Response.json(upstream.status === 404 ? { detail: "unknown match" } : UNAVAILABLE, {
        status: upstream.status === 404 ? 404 : 502,
      });
    }
    return new Response(upstream.body, { headers: STREAM_HEADERS });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502 });
  }
}
