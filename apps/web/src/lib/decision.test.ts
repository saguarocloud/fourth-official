import { describe, expect, it } from "vitest";

import { cleanReason, parseDecision } from "./decision";

describe("cleanReason", () => {
  it("keeps one trimmed line", () => {
    expect(cleanReason("  Not our tone  ")).toBe("Not our tone");
    expect(cleanReason("Ton: zu reißerisch")).toBe("Ton: zu reißerisch");
  });

  it.each([
    ["", "blank"],
    ["   ", "spaces"],
    ["a\nb", "two lines"],
    ["see https://x.example", "a link"],
    ["visit www.x.example", "a web address"],
    ["a‮b", "a direction override"],
    ["a​b", "a zero-width space"],
    ["x".repeat(201), "too long"],
  ])("refuses %j (%s)", (text) => {
    expect(cleanReason(text)).toBeNull();
  });
});

describe("parseDecision", () => {
  it("accepts an approval and a rejection with its reason", () => {
    expect(parseDecision({ decision: "approved", generation: 2 })).toEqual({
      decision: "approved",
      generation: 2,
    });
    expect(parseDecision({ decision: "rejected", generation: 0, reason: " Off tone " })).toEqual({
      decision: "rejected",
      generation: 0,
      reason: "Off tone",
    });
  });

  it.each([
    null,
    [],
    "approved",
    { decision: "approved", generation: -1 },
    { decision: "approved", generation: 1.5 },
    { decision: "approved", generation: 1, reason: "Fine" },
    { decision: "rejected", generation: 1, reason: 7 },
  ])("refuses %j", (value) => {
    expect(parseDecision(value)).toBeNull();
  });
});
