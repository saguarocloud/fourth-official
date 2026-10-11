import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

const params = (matchId: string) => ({ params: Promise.resolve({ matchId }) });

describe("GET /api/matches/[matchId]/stream", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("passes the event stream through with Last-Event-ID", async () => {
    const fetch = vi.fn(() =>
      Promise.resolve(
        new Response("id: 1:1\nevent: clock\ndata: {}\n\n", {
          status: 200,
          headers: { "Content-Type": "text/event-stream; charset=utf-8" },
        }),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const request = new Request("http://studio/api/matches/m42/stream", {
      headers: { "last-event-id": "1:4" },
    });

    const response = await GET(request, params("m42"));

    expect(response.headers.get("content-type")).toBe("text/event-stream");
    // no-transform: nothing between here and the browser may compress, and so buffer, events.
    expect(response.headers.get("cache-control")).toBe("no-cache, no-transform");
    expect(await response.text()).toContain("event: clock");
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/matches/m42/stream",
      expect.objectContaining({ headers: { "Last-Event-ID": "1:4" } }),
    );
  });

  it("refuses an upstream answer that is not an event stream", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("<html>", { status: 200 }))),
    );

    const response = await GET(new Request("http://studio/x"), params("m42"));

    expect(response.status).toBe(502);
  });

  it("refuses a malformed match id without calling the API", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    const response = await GET(new Request("http://studio/x"), params("m42%2F..%2Fadmin"));

    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    [404, 404],
    [503, 502],
  ])("maps an upstream %i to %i", async (upstream, expected) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: upstream }))),
    );

    expect((await GET(new Request("http://studio/x"), params("m42"))).status).toBe(expected);
  });

  it("answers 502 when the API is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("fetch failed"))),
    );

    expect((await GET(new Request("http://studio/x"), params("m42"))).status).toBe(502);
  });
});
