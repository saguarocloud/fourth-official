import { describe, expect, it } from "vitest";

import { DEMO_MATCHDAY } from "@/fixtures/matchday";

import { clubByCode, summarise, type Match } from "./matchday";

const baseMatch: Match = {
  id: "m1",
  home: "HCY",
  away: "NGT",
  homeScore: 1,
  awayScore: 0,
  minute: 68,
  second: 4,
  period: 2,
  status: "live",
  featured: true,
  itemsPerMinute: 3.5,
  pendingApprovals: 2,
  corrections: 1,
  p95LatencyMs: 4100,
  onAir: { northlight: true, "tribuna-austral": false, rheinblick: false },
};

describe("summarise", () => {
  it("totals activity across live matches", () => {
    const summary = summarise(
      [
        baseMatch,
        { ...baseMatch, id: "m2", itemsPerMinute: 1.5, pendingApprovals: 1, corrections: 0 },
      ],
      { sloMs: 8000, costCents: 1234 },
    );

    expect(summary).toMatchObject({
      liveMatches: 2,
      itemsPerMinute: 5,
      pendingApprovals: 3,
      corrections: 1,
      costCents: 1234,
    });
  });

  it("reports the worst p95 latency and whether it is inside the SLO", () => {
    const within = summarise([baseMatch, { ...baseMatch, id: "m2", p95LatencyMs: 6900 }], {
      sloMs: 8000,
      costCents: 0,
    });
    const breached = summarise([{ ...baseMatch, p95LatencyMs: 8400 }], {
      sloMs: 8000,
      costCents: 0,
    });

    expect(within).toMatchObject({ p95LatencyMs: 6900, withinSlo: true });
    expect(breached).toMatchObject({ p95LatencyMs: 8400, withinSlo: false });
  });

  it("does not count finished matches as live", () => {
    const summary = summarise([{ ...baseMatch, status: "full_time" }], {
      sloMs: 8000,
      costCents: 0,
    });

    expect(summary.liveMatches).toBe(0);
  });
});

describe("clubByCode", () => {
  it("resolves a fictional club by its short code", () => {
    expect(clubByCode("HCY").name).toBe("Harbour City");
  });
});

describe("the demo matchday fixture", () => {
  it("features exactly one match", () => {
    expect(DEMO_MATCHDAY.matches.filter((m) => m.featured)).toHaveLength(1);
  });

  it("reports every partner's tally on every match", () => {
    const partnerIds = DEMO_MATCHDAY.partners.map((p) => p.id).sort();
    for (const match of DEMO_MATCHDAY.matches) {
      expect(Object.keys(match.onAir).sort()).toEqual(partnerIds);
    }
  });

  it("lists activity newest first", () => {
    const order = DEMO_MATCHDAY.activity.map((a) => a.sequence);
    expect(order).toEqual([...order].sort((a, b) => b - a));
  });
});
