import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

const PARAMS = {
  tenantId: "tribuna-austral",
  matchId: "m42",
  itemId: "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1",
};
const STUDIO = {
  host: "studio.example",
  origin: "https://studio.example",
  "content-type": "application/json",
  "x-requested-by": "fourth-official",
  "sec-fetch-site": "same-origin",
};
const BODY = { decision: "approved", generation: 1 };

function call(
  body: unknown = BODY,
  headers: Record<string, string> = STUDIO,
  params: Record<string, string> = PARAMS,
) {
  const request = new Request("http://0.0.0.0:3000/api/decision", {
    method: "POST",
    headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
  return POST(request, { params: Promise.resolve(params) } as never);
}

describe("POST a decision", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("forwards a valid decision to the item's own address, as the studio", async () => {
    const fetch = vi.fn(() => Promise.resolve(Response.json({ state: "on_air" })));
    vi.stubGlobal("fetch", fetch);

    const response = await call({ decision: "rejected", generation: 3, reason: "Not our tone" });

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/tenants/tribuna-austral/matches/m42/items/it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v1/decision",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-By": "fourth-official" },
        body: JSON.stringify({ decision: "rejected", generation: 3, reason: "Not our tone" }),
        cache: "no-store",
        signal: expect.any(AbortSignal),
      },
    );
  });

  it.each([
    ["the API's refusals", 409, { detail: "this item is not awaiting a decision" }],
    ["full time", 410, { detail: "the match has reached full time; held items stay off air" }],
    ["no room yet", 503, { detail: "no room on air this minute; try again shortly" }],
    ["not found", 404, { detail: "no such item on this match's feed" }],
  ])("passes %s through", async (_, status, detail) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(detail, { status }))),
    );

    const response = await call();

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual(detail);
  });

  it.each([
    ["another site", { ...STUDIO, origin: "https://evil.example" }],
    ["a cross-site fetch", { ...STUDIO, "sec-fetch-site": "cross-site" }],
    ["no studio header", { ...STUDIO, "x-requested-by": "" }],
    ["a form post", { ...STUDIO, "content-type": "application/x-www-form-urlencoded" }],
  ])("refuses %s without calling the API", async (_, headers) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    expect((await call(BODY, headers)).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    ["an unknown decision", { decision: "maybe", generation: 1 }],
    ["no run", { decision: "approved" }],
    ["a rejection with no reason", { decision: "rejected", generation: 1 }],
    ["a long reason", { decision: "rejected", generation: 1, reason: "x".repeat(201) }],
    ["two lines", { decision: "rejected", generation: 1, reason: "a\nb" }],
    ["an extra field", { decision: "approved", generation: 1, editor: "Someone" }],
    ["not json", "{"],
    ["too much", JSON.stringify({ ...BODY, pad: "x".repeat(5000) })],
  ])("refuses %s without calling the API", async (_, body) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    expect((await call(body)).status).toBe(422);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    ["partner", { ...PARAMS, tenantId: "Evil" }],
    ["match", { ...PARAMS, matchId: "../x" }],
    ["item", { ...PARAMS, itemId: "it-x/../../matchday" }],
  ])("refuses a malformed %s without calling the API", async (_, params) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    expect((await call(BODY, STUDIO, params)).status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("answers 502 when the API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("down"))),
    );

    expect((await call()).status).toBe(502);
  });
});
