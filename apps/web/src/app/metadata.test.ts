import { describe, expect, it } from "vitest";

import { metadata } from "./metadata";

describe("site metadata", () => {
  it("uses the product name as the page title", () => {
    expect(metadata.title).toBe("Fourth Official");
  });

  it("describes the product without default scaffold copy", () => {
    expect(metadata.description).toMatch(/AI match intelligence/);
  });
});
