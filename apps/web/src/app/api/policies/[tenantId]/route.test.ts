import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import fixture from "@/fixtures/policy-history-rheinblick.json";

import { GET, POST } from "./route";

const TENANT = "rheinblick-sport";
const STUDIO = {
  "x-requested-by": "fourth-official",
  "content-type": "application/json",
  host: "studio.example",
  origin: "https://studio.example",
};
const EDIT = { policy: { maxItemsPerMinute: 3 }, baseVersion: 3, reason: "Quieter" };

function get(tenantId = TENANT) {
  return GET(new Request(`https://studio.example/api/policies/${tenantId}`), {
    params: Promise.resolve({ tenantId }),
  });
}

function post(body: unknown = EDIT, headers: Record<string, string> = STUDIO, tenantId = TENANT) {
  const request = new Request(`https://studio.example/api/policies/${tenantId}`, {
    method: "POST",
    headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
  return POST(request, { params: Promise.resolve({ tenantId }) });
}

describe("the policy history and edit routes", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("passes a partner's history through, never cached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(fixture))),
    );

    const response = await get();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(fixture);
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("knows only the three partners", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    expect((await get("../admin")).status).toBe(404);
    expect((await post(EDIT, STUDIO, "someone")).status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("forwards an edit from the studio, naming itself to the API", async () => {
    const change = { version: 4, action: "edited" };
    const fetch = vi.fn(() => Promise.resolve(Response.json(change)));
    vi.stubGlobal("fetch", fetch);

    const response = await post();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(change);
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`http://127.0.0.1:8000/api/policies/${TENANT}`);
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      "X-Requested-By": "fourth-official",
    });
    expect(JSON.parse(init.body as string)).toEqual(EDIT);
    expect(init.redirect).toBe("error");
  });

  it.each([
    ["from another site", { ...STUDIO, origin: "https://evil.example" }],
    ["without the studio's header", { ...STUDIO, "x-requested-by": "" }],
    ["as a form", { ...STUDIO, "content-type": "application/x-www-form-urlencoded" }],
  ])("refuses an edit %s", async (_, headers) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    expect((await post(EDIT, headers)).status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    ["not JSON", "{policy"],
    ["with fields the API does not take", { ...EDIT, dutyEditor: "Me" }],
    ["with no reason", { policy: {}, baseVersion: 1 }],
    ["too large", { ...EDIT, yaml: "x".repeat(100_000), policy: undefined }],
  ])("refuses an edit %s before it reaches the API", async (_, body) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);

    const status = (await post(body)).status;

    expect([413, 422]).toContain(status);
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([409, 422, 429, 503])("passes the API's %i through with its reason", async (code) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({ detail: "why" }, { status: code }))),
    );

    const response = await post();

    expect(response.status).toBe(code);
    expect(await response.json()).toEqual({ detail: "why" });
  });

  it("is a gateway error when the API fails otherwise", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("down"))),
    );

    expect((await post()).status).toBe(502);
  });
});
