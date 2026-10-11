/**
 * The match API, reached only from the web server. The browser talks to this app's own routes,
 * which forward to the API: the API's address never reaches the client, and no CORS is needed.
 */

const API_URL =
  /^(https:\/\/[a-z0-9][a-z0-9.-]{1,240}\.azurecontainerapps\.io|http:\/\/(127\.0\.0\.1|localhost)(:[0-9]{1,5})?)\/?$/;

/** The API's base URL, from API_URL: HTTPS on Azure Container Apps, or plain HTTP locally. */
export function apiBase(): string {
  const value = process.env.API_URL?.trim() ?? "";
  if (!API_URL.test(value)) {
    throw new Error("API_URL must be the match API's address");
  }
  return value.replace(/\/$/, "");
}

export { isMatchId } from "@/lib/matchId";

/** True unless a browser says the request came from another site. Compares the Origin's host
 * with the host the request was sent to (as the ingress forwards it). */
export function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (origin === null) return true;
  // Behind several proxies the forwarded host is a list; the first is the one the browser used.
  const forwarded = request.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = forwarded || request.headers.get("host");
  try {
    return host !== null && new URL(origin).host === host;
  } catch {
    return false;
  }
}

/** How long a plain request to the match API may take before the studio calls it unavailable. */
export const UPSTREAM_TIMEOUT_MS = 10_000;

export const UNAVAILABLE = { detail: "The match service is unavailable. Try again shortly." };
