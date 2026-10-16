import { describe, expect, it } from "vitest";

import { clubByCode, matchdayVerdict } from "./matchday";

describe("clubByCode", () => {
  it("resolves a fictional club by its short code", () => {
    expect(clubByCode("HCY").name).toBe("Harbour City");
  });
});

describe("clubByCode for a club the wall does not know", () => {
  it("falls back to the code itself", () => {
    expect(clubByCode("XYZ")).toEqual({ code: "XYZ", name: "XYZ" });
  });
});

describe("matchdayVerdict", () => {
  const healthy = {
    liveMatches: 3,
    pendingApprovals: 0,
    corrections: 0,
    p95LatencyMs: 4100,
    sloMs: 8000,
    withinSlo: true,
    costMicrousd: 0,
  };

  it("says everything is under control when nothing needs a person", () => {
    expect(matchdayVerdict(healthy)).toEqual({
      tone: "green",
      text: "All 3 matches under control. Nothing awaits approval.",
    });
  });

  it("speaks of a single live match in the singular", () => {
    expect(matchdayVerdict({ ...healthy, liveMatches: 1 }).text).toBe(
      "The live match is under control. Nothing awaits approval.",
    );
  });

  it("is neutral when no match is live", () => {
    expect(matchdayVerdict({ ...healthy, liveMatches: 0, p95LatencyMs: null })).toEqual({
      tone: "neutral",
      text: "No matches live. Nothing awaits approval.",
    });
  });

  it("asks for attention when items await approval", () => {
    expect(matchdayVerdict({ ...healthy, pendingApprovals: 3 })).toEqual({
      tone: "amber",
      text: "All 3 matches under control. 3 items await approval.",
    });
  });

  it("uses the singular for one item", () => {
    expect(matchdayVerdict({ ...healthy, pendingApprovals: 1 }).text).toBe(
      "All 3 matches under control. 1 item awaits approval.",
    );
  });

  it("raises an alarm when latency leaves the SLO, whatever else is true", () => {
    expect(
      matchdayVerdict({ ...healthy, pendingApprovals: 2, withinSlo: false, p95LatencyMs: 9100 }),
    ).toEqual({
      tone: "red",
      text: "Event-to-air latency is outside the SLO. Investigate before more items publish.",
    });
  });
});
