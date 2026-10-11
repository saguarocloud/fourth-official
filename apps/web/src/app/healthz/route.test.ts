import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { connection } = vi.hoisted(() => ({ connection: vi.fn(() => Promise.resolve()) }));
vi.mock("next/server", () => ({ connection }));

import { GET } from "./route";

describe("GET /healthz", () => {
  beforeEach(() => {
    connection.mockClear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("reports ok with the service name and the deployed version", async () => {
    vi.stubEnv("APP_VERSION", "abc1234");

    const response = await GET();

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      status: "ok",
      service: "fourth-official-web",
      version: "abc1234",
    });
  });

  it("falls back to dev when no version is set", async () => {
    vi.stubEnv("APP_VERSION", "");

    expect(await (await GET()).json()).toMatchObject({ version: "dev" });
  });

  it("is never cached", async () => {
    expect((await GET()).headers.get("cache-control")).toBe("no-store");
  });

  it("opts out of prerendering so every probe hits the live server", async () => {
    await GET();

    expect(connection).toHaveBeenCalledOnce();
  });
});
