import { describe, expect, it } from "vitest";

import { isItemId } from "./itemId";

describe("isItemId", () => {
  it.each([
    "it-northlight-sport-in-m42-goal-HCY-s0287-a1-v1",
    "it-tribuna-austral-in-m42-goal-HCY-s0287-a1-v2",
  ])("accepts %s", (id) => expect(isItemId(id)).toBe(true));

  it.each([
    ["no prefix", "northlight-in-m42-v1"],
    ["a path", "it-x/../../admin"],
    ["a query", "it-x-v1?a=b"],
    ["an encoded slash", "it-x-%2F"],
    ["too long", `it-x-${"a".repeat(130)}`],
    ["nothing", ""],
  ])("refuses %s", (_, id) => expect(isItemId(id)).toBe(false));
});
