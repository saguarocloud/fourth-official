import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

const STUDIO = {
  "x-requested-by": "fourth-official",
  "content-type": "application/json",
  host: "studio.example",
  origin: "https://studio.example",
};

function post(body: unknown, headers: Record<string, string> = STUDIO) {
  return POST(
    new Request("https://studio.example/api/policies/reset", {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    }),
  );
}

describe("the reset route", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("forwards a reset from the studio with its reason", async () => {
    const fetch = vi.fn(() => Promise.resolve(Response.json({ changes: [] })));
    vi.stubGlobal("fetch", fetch);

    const response = await post({ reason: "End of the demo" });

    expect(response.status).toBe(200);
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/policies/reset");
    expect(JSON.parse(init.body as string)).toEqual({ reason: "End of the demo" });
  });

  it("refuses a reset from another site, or without a reason", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    expect(
      (await post({ reason: "x" }, { ...STUDIO, origin: "https://evil.example" })).status,
    ).toBe(403);
    expect((await post({})).status).toBe(422);
    expect(fetch).not.toHaveBeenCalled();
  });
});
