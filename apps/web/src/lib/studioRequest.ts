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

/** The JSON body, or null if it is larger than `limit` bytes or not JSON. */
export async function jsonBody(request: Request, limit: number): Promise<unknown> {
  const text = await request.text();
  if (new TextEncoder().encode(text).length > limit) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export function refuse(status: number, detail: string): Response {
  return Response.json({ detail }, { status, headers: NO_STORE });
}
