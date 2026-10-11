import { apiBase, isMatchId, UNAVAILABLE } from "@/lib/matchApi";
import { clientOf, streamSlots } from "@/lib/streamSlots";

/** Enough for a producer with several tabs; far below the API's limit of 200 streams. */
export const MAX_STREAMS_PER_CLIENT = 6;
const slots = streamSlots(MAX_STREAMS_PER_CLIENT);

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
  const release = slots.claim(clientOf(request));
  if (release === null) {
    return Response.json(
      { detail: "Too many live streams are open from here. Close one and try again." },
      { status: 429, headers: { "Retry-After": "30" } },
    );
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
      release();
      // Close what the API sent, so its connection is not held until garbage collection.
      await upstream.body?.cancel().catch(() => undefined);
      return Response.json(upstream.status === 404 ? { detail: "unknown match" } : UNAVAILABLE, {
        status: upstream.status === 404 ? 404 : 502,
      });
    }
    return new Response(releasingOnClose(upstream.body, release), { headers: STREAM_HEADERS });
  } catch {
    release();
    return Response.json(UNAVAILABLE, { status: 502 });
  }
}

/** The upstream body, passed through; the client's slot is released when it ends or is closed. */
function releasingOnClose(
  body: ReadableStream<Uint8Array>,
  release: () => void,
): ReadableStream<Uint8Array> {
  const reader = body.getReader();
  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (done) {
          release();
          controller.close();
        } else {
          controller.enqueue(value);
        }
      } catch (error) {
        release();
        controller.error(error);
      }
    },
    async cancel(reason) {
      release();
      await reader.cancel(reason);
    },
  });
}
