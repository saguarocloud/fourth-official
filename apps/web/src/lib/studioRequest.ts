/** Requests that change something may come only from this app's own pages: a script on this
 * origin that names itself and sends JSON. A cross-site form can do none of that, and a
 * cross-site fetch is refused by its own headers (ADR-011). */
import { sameOrigin } from "@/lib/matchApi";

export const STUDIO_HEADER = "x-requested-by";
export const STUDIO = "fourth-official";
export const NO_STORE = { "Cache-Control": "no-store" };

export function fromTheStudio(request: Request): boolean {
  const site = request.headers.get("sec-fetch-site");
  return (
    sameOrigin(request) &&
    (site === null || site === "same-origin") &&
    request.headers.get(STUDIO_HEADER) === STUDIO &&
    (request.headers.get("content-type") ?? "").split(";")[0]?.trim() === "application/json"
  );
}

/** Whether the request declares a body larger than `limit` bytes. */
export function declaresMoreThan(request: Request, limit: number): boolean {
  const declared = Number(request.headers.get("content-length") ?? 0);
  return Number.isFinite(declared) && declared > limit;
}

// The body's bytes, read only as far as `limit`: a body sent in chunks with no length declared
// is cut off there rather than buffered whole first.
async function bytesUpTo(request: Request, limit: number): Promise<Uint8Array | null> {
  if (!request.body) return new Uint8Array();
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > limit) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let at = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, at);
    at += chunk.byteLength;
  }
  return bytes;
}

/** The JSON body, or null if it is larger than `limit` bytes or not JSON. */
export async function jsonBody(request: Request, limit: number): Promise<unknown> {
  const bytes = await bytesUpTo(request, limit);
  if (!bytes) return null;
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as unknown;
  } catch {
    return null;
  }
}

export function refuse(status: number, detail: string): Response {
  return Response.json({ detail }, { status, headers: NO_STORE });
}
