import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/server", () => ({ connection: vi.fn(() => Promise.resolve()) }));

import { GET } from "./route";

const TENANTS = {
  tenants: [
    {
      tenantId: "tribuna-austral",
      displayName: "Tribuna Austral",
      locale: "es-MX",
      disclosureMode: "label-all",
      approvalRequired: ["insight", "recap"],
      dutyEditor: "T. Ibarra",
    },
  ],
};

describe("GET /api/tenants", () => {
  beforeEach(() => vi.stubEnv("API_URL", "http://127.0.0.1:8000"));
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("passes the partners through", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json(TENANTS))),
    );

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(TENANTS);
  });

  it("answers 502 when the API fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(Response.json({}, { status: 500 }))),
    );

    expect((await GET()).status).toBe(502);
  });
});
