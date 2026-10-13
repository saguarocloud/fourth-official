import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

describe("the policies route", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("passes every partner's current policy through, never cached", async () => {
    const body = { policies: [{ tenantId: "rheinblick-sport", version: 3 }] };
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(body))),
    );

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(body);
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("is a gateway error when the API does not answer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("down"))),
    );

    expect((await GET()).status).toBe(502);
  });
});
