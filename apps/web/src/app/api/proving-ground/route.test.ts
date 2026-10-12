import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import fixture from "@/fixtures/proving-ground.json";

import { GET } from "./route";

function call(headers: Record<string, string> = {}) {
  return GET(new Request("http://0.0.0.0:3000/api/proving-ground", { headers }));
}

describe("GET the Proving Ground", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("passes the API's recorded runs through, cacheable for a few minutes", async () => {
    const fetch = vi.fn(() => Promise.resolve(Response.json(fixture)));
    vi.stubGlobal("fetch", fetch);

    const response = await call();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(fixture);
    expect(response.headers.get("cache-control")).toBe("public, max-age=300");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/proving-ground", {
      cache: "no-store",
      redirect: "error",
      signal: expect.any(AbortSignal),
    });
  });

  it("says when the results are not available", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({ detail: "x" }, { status: 503 }))),
    );

    const response = await call();

    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("passes a busy API on, with when to try again", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          Response.json({ detail: "x" }, { status: 429, headers: { "Retry-After": "30" } }),
        ),
      ),
    );

    const response = await call({ "x-forwarded-for": "198.51.100.9" });

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("30");
  });

  it.each([
    ["an unexpected status", () => Promise.resolve(Response.json({}, { status: 500 }))],
    ["no answer", () => Promise.reject(new TypeError("fetch failed"))],
  ])("is a gateway error on %s", async (_, answer) => {
    vi.stubGlobal("fetch", vi.fn(answer));

    const response = await call();

    expect(response.status).toBe(502);
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("limits each visitor's reads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(fixture))),
    );
    const visitor = { "x-forwarded-for": "198.51.100.77" };

    const answers = [];
    for (let i = 0; i < 61; i += 1) answers.push((await call(visitor)).status);

    expect(answers.at(-1)).toBe(429);
  });
});
