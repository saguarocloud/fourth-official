import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET, READS_PER_MINUTE } from "./route";

const ITEM = "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1";

function call(itemId = ITEM, headers: Record<string, string> = {}) {
  const request = new Request(`http://0.0.0.0:3000/api/items/${itemId}/provenance`, { headers });
  return GET(request, { params: Promise.resolve({ itemId }) } as never);
}

describe("GET an item's provenance", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("asks the API for that item only, and passes its answer through", async () => {
    const body = { provenance: null, verification: { valid: false, reason: "x" } };
    const fetch = vi.fn(() => Promise.resolve(Response.json(body)));
    vi.stubGlobal("fetch", fetch);

    const response = await call(ITEM, { "x-forwarded-for": "203.0.113.4" });

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual(body);
    expect(fetch).toHaveBeenCalledWith(`http://127.0.0.1:8000/api/items/${ITEM}/provenance`, {
      headers: { "X-Forwarded-For": "203.0.113.4" },
      cache: "no-store",
      redirect: "error",
      signal: expect.any(AbortSignal),
    });
  });

  it.each([
    [404, { detail: "no provenance for this item" }],
    [429, { detail: "too many reads from here; try again shortly" }],
    [503, { detail: "records cannot be read right now" }],
  ])("passes a %i through", async (status, body) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(body, { status }))),
    );

    const response = await call();

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual(body);
  });

  it.each(["<script>", "it-x/../../matchday", "x".repeat(200)])(
    "refuses a malformed item %j without calling the API",
    async (itemId) => {
      const fetch = vi.fn();
      vi.stubGlobal("fetch", fetch);

      expect((await call(itemId)).status).toBe(404);
      expect(fetch).not.toHaveBeenCalled();
    },
  );

  it("limits how often one visitor reads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({}))),
    );
    const visitor = { "x-forwarded-for": "198.51.100.9" };
    const answers = [];
    for (let i = 0; i < READS_PER_MINUTE + 1; i += 1)
      answers.push((await call(ITEM, visitor)).status);

    expect(answers.slice(0, -1).every((s) => s === 200)).toBe(true);
    expect(answers.at(-1)).toBe(429);
  });

  it("answers 502 when the API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("down"))),
    );

    expect((await call()).status).toBe(502);
  });
});
