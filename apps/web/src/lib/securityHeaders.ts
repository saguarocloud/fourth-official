/**
 * Browser protections for every response. The studio loads nothing from other origins, so the
 * Content Security Policy allows only this one.
 *
 * Scripts need 'unsafe-inline': Next.js streams the page's data in inline scripts, and pages are
 * prerendered (Partial Prerendering), which rules out per-request nonces; their content varies, so
 * hashes cannot list them either. Checked in a browser: without it every page fails to hydrate.
 * The risk it leaves is small here: every piece of text, including model output, renders through
 * React as text (no raw HTML anywhere), and no script can load from another origin.
 */

interface Mode {
  /** Development needs eval for React's error overlays; production never does. */
  readonly dev: boolean;
}

export interface Header {
  readonly key: string;
  readonly value: string;
}

export function contentSecurityPolicy({ dev }: Mode): string {
  const directives = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
    // Inline scripts must run; inline event-handler attributes never need to.
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    // Production only: some browsers would upgrade a plain-http localhost and break the page.
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ];
  return directives.join("; ");
}

export function securityHeaders(mode: Mode): Header[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(mode) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    {
      key: "Permissions-Policy",
      value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    },
  ];
}
