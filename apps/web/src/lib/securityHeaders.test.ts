import { describe, expect, it } from "vitest";

import { contentSecurityPolicy, securityHeaders } from "./securityHeaders";

function directives(policy: string): Map<string, string[]> {
  return new Map(
    policy
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const [name, ...values] = part.split(/\s+/);
        return [name!, values];
      }),
  );
}

describe("contentSecurityPolicy", () => {
  it("allows only this origin, and nothing framing or embedding the studio", () => {
    const policy = directives(contentSecurityPolicy({ dev: false }));

    expect(policy.get("default-src")).toEqual(["'self'"]);
    expect(policy.get("connect-src")).toEqual(["'self'"]);
    expect(policy.get("object-src")).toEqual(["'none'"]);
    expect(policy.get("frame-ancestors")).toEqual(["'none'"]);
    expect(policy.get("base-uri")).toEqual(["'self'"]);
    expect(policy.get("form-action")).toEqual(["'self'"]);
    expect(policy.has("upgrade-insecure-requests")).toBe(true);
  });

  it("blocks inline event handlers even though inline scripts run", () => {
    expect(directives(contentSecurityPolicy({ dev: false })).get("script-src-attr")).toEqual([
      "'none'",
    ]);
  });

  it("upgrades insecure requests in production only, so plain http works locally", () => {
    expect(contentSecurityPolicy({ dev: true })).not.toContain("upgrade-insecure-requests");
  });

  it("never allows eval in production, only in development", () => {
    expect(contentSecurityPolicy({ dev: false })).not.toContain("unsafe-eval");
    expect(contentSecurityPolicy({ dev: true })).toContain("'unsafe-eval'");
  });

  it("allows scripts only from this origin and inline (the page's streamed data)", () => {
    const policy = directives(contentSecurityPolicy({ dev: false }));

    expect(policy.get("script-src")).toEqual(["'self'", "'unsafe-inline'"]);
  });

  it("is one line", () => {
    expect(contentSecurityPolicy({ dev: false })).not.toMatch(/\n/);
  });
});

describe("securityHeaders", () => {
  it("sets the browser protections a studio app needs", () => {
    const headers = new Map(securityHeaders({ dev: false }).map((h) => [h.key, h.value]));

    expect(headers.get("Content-Security-Policy")).toBe(contentSecurityPolicy({ dev: false }));
    expect(headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(headers.get("X-Frame-Options")).toBe("DENY");
    expect(headers.get("Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    expect(headers.get("Strict-Transport-Security")).toBe("max-age=63072000; includeSubDomains");
    expect(headers.get("Cross-Origin-Opener-Policy")).toBe("same-origin");
    expect(headers.get("Permissions-Policy")).toBe(
      "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    );
  });
});
