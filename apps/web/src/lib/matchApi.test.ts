import { afterEach, describe, expect, it, vi } from "vitest";

import { apiBase, isMatchId, sameOrigin } from "./matchApi";

describe("apiBase", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("uses API_URL without a trailing slash", () => {
    vi.stubEnv("API_URL", "https://ca-api-x.happyhill.eastus2.azurecontainerapps.io/");

    expect(apiBase()).toBe("https://ca-api-x.happyhill.eastus2.azurecontainerapps.io");
  });

  it("allows plain http only on this machine", () => {
    vi.stubEnv("API_URL", "http://127.0.0.1:8000");

    expect(apiBase()).toBe("http://127.0.0.1:8000");
  });

  it.each(["", "ftp://x", "http://evil.example", "https://evil.example/path?x=1", "not a url"])(
    "refuses %s",
    (value) => {
      vi.stubEnv("API_URL", value);

      expect(() => apiBase()).toThrow(/API_URL/);
    },
  );
});

describe("isMatchId", () => {
  it.each([
    ["m42", true],
    ["m123456789012", true],
    ["m", false],
    ["42", false],
    ["m42/../x", false],
  ])("%s -> %s", (value, expected) => {
    expect(isMatchId(value)).toBe(expected);
  });
});

describe("sameOrigin", () => {
  const request = (headers: Record<string, string>) =>
    new Request("http://0.0.0.0:3000/api/matchday", { method: "POST", headers });

  it("accepts the host the ingress forwarded, and requests without an origin", () => {
    expect(
      sameOrigin(
        request({ origin: "https://studio.example", "x-forwarded-host": "studio.example" }),
      ),
    ).toBe(true);
    expect(sameOrigin(request({ origin: "http://localhost:3000", host: "localhost:3000" }))).toBe(
      true,
    );
    expect(sameOrigin(request({}))).toBe(true);
  });

  it("takes the first host when proxies forwarded several", () => {
    expect(
      sameOrigin(
        request({
          origin: "https://studio.example",
          "x-forwarded-host": "studio.example, internal.example",
        }),
      ),
    ).toBe(true);
  });

  it.each<Record<string, string>>([
    { origin: "https://evil.example", host: "studio.example" },
    { origin: "null", host: "studio.example" },
    { origin: "https://studio.example" },
  ])("refuses %o", (headers) => {
    expect(sameOrigin(request(headers))).toBe(false);
  });
});
