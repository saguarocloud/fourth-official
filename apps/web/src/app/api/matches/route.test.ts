import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(() => Promise.resolve()) }));

import { GET } from "./route";

describe("GET /api/matches", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("passes the match API's list through, never cached", async () => {
    const fetch = vi.fn(() => Promise.resolve(Response.json({ matches: [] })));
    vi.stubGlobal("fetch", fetch);

    const response = await GET();

    expect(await response.json()).toEqual({ matches: [] });
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/matches", {
      cache: "no-store",
      signal: expect.any(AbortSignal),
    });
  });

  it.each([
    ["an error status", () => Promise.resolve(new Response("", { status: 500 }))],
    ["a network failure", () => Promise.reject(new TypeError("fetch failed"))],
  ])("answers 502 on %s", async (_, answer) => {
    vi.stubGlobal("fetch", vi.fn(answer));

    const response = await GET();

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({
      detail: "The match service is unavailable. Try again shortly.",
    });
  });
});
