import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(() => Promise.resolve()) }));

import { GET, POST } from "./route";

function request(headers: Record<string, string> = {}): Request {
  return new Request("http://0.0.0.0:3000/api/matchday", {
    method: "POST",
    headers: { host: "studio.example", ...headers },
  });
}

describe("POST /api/matchday", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("starts the matchday with the studio header", async () => {
    const fetch = vi.fn(() =>
      Promise.resolve(Response.json({ status: "started" }, { status: 202 })),
    );
    vi.stubGlobal("fetch", fetch);

    const response = await POST(request({ origin: "https://studio.example" }));

    expect(response.status).toBe(202);
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/matchday", {
      method: "POST",
      headers: { "X-Requested-By": "fourth-official" },
      cache: "no-store",
      signal: expect.any(AbortSignal),
    });
  });

  it("passes a busy answer through", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          Response.json({ detail: "a matchday is already running" }, { status: 409 }),
        ),
      ),
    );

    const response = await POST(request());

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({ detail: "a matchday is already running" });
  });

  it("refuses a request from another site without calling the API", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    const response = await POST(request({ origin: "https://evil.example" }));

    expect(response.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("answers 502 when the API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({}, { status: 503 }))),
    );

    expect((await POST(request())).status).toBe(502);
  });
});

describe("GET /api/matchday", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("says whether the matchday may start", async () => {
    const answer = { ready: false, reason: "cooling down", readyAt: "2026-10-11T12:00:00+00:00" };
    const fetch = vi.fn(() => Promise.resolve(Response.json(answer)));
    vi.stubGlobal("fetch", fetch);

    const response = await GET();

    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/matchday", {
      cache: "no-store",
      signal: expect.any(AbortSignal),
    });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(await response.json()).toEqual(answer);
  });

  it("is unavailable when the match API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("", { status: 500 }))),
    );

    expect((await GET()).status).toBe(502);
  });
});
