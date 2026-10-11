import { describe, expect, it } from "vitest";

import { plural } from "./plural";

describe("plural", () => {
  it("names one and many", () => {
    expect([
      plural(1, "item", "items"),
      plural(0, "item", "items"),
      plural(3, "item", "items"),
    ]).toEqual(["1 item", "0 items", "3 items"]);
  });
});
