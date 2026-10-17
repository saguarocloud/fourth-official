import { describe, expect, it } from "vitest";

import type { OperationsReport } from "@/contracts/operations";
import type { MatchdayWall } from "@/contracts/wall";
import operationsFixture from "@/fixtures/operations.json";
import wallFixture from "@/fixtures/wall.json";

import { controlRoom, FEATURED_MATCH, parseWall } from "./controlRoom";
import { totals } from "./operations";

const WALL = wallFixture as unknown as MatchdayWall;
const OPERATIONS = operationsFixture as unknown as OperationsReport;

describe("parseWall", () => {
  it("reads a wall shaped as the API sends it", () => {
    expect(parseWall(WALL)).toEqual(WALL);
  });

  it("refuses a match or an item in a state it does not know", () => {
    expect(parseWall({ ...WALL, matches: [{ ...WALL.matches[0], state: "paused" }] })).toBeNull();
    expect(
      parseWall({ ...WALL, activity: [{ ...WALL.activity[0], state: "broadcasting" }] }),
    ).toBeNull();
  });

  it("refuses anything else", () => {
    expect(parseWall(null)).toBeNull();
    expect(parseWall({ ...WALL, matches: "m42" })).toBeNull();
    expect(parseWall({ ...WALL, matches: [{ ...WALL.matches[0], items: -1 }] })).toBeNull();
    expect(parseWall({ ...WALL, activity: [{ ...WALL.activity[0], headline: 3 }] })).toBeNull();
  });
});

describe("controlRoom", () => {
  it("shows every match with its score, clock and partners on air, the featured one first", () => {
    const room = controlRoom(WALL, OPERATIONS);

    expect(room.matches.map((m) => m.id)[0]).toBe(FEATURED_MATCH);
    const m42 = room.matches.find((m) => m.id === "m42")!;
    const wall = WALL.matches.find((m) => m.matchId === "m42")!;
    expect([m42.homeScore, m42.awayScore]).toEqual([wall.score.home, wall.score.away]);
    expect(m42.clock).toEqual(wall.clock);
    expect([...m42.onAir].sort()).toEqual([...wall.onAir].sort());
    expect(m42.status).toBe("full_time");
  });

  it("takes each match's latency and throughput from what operations measured", () => {
    const room = controlRoom(WALL, OPERATIONS);
    const m42 = room.matches.find((m) => m.id === "m42")!;
    const measured = OPERATIONS.matches.find((m) => m.matchId === "m42")!;

    expect(m42.p95LatencyMs).toBe(measured.onAir.p95Ms);
    // Both from the one report, so the rate never mixes two readings taken apart.
    const items = measured.partners.reduce((n, p) => n + p.items, 0);
    expect(m42.itemsPerMinute).toBeCloseTo((items * 60_000) / measured.runMs);
  });

  it("sums the matchday against the on-air objective, and costs it from the measured run", () => {
    const { summary } = controlRoom(WALL, OPERATIONS);
    const p95 = OPERATIONS.objectives.find((o) => o.key === "on_air_p95")!;

    expect(summary.p95LatencyMs).toBe(p95.measuredMs);
    expect(summary.sloMs).toBe(p95.targetMs);
    expect(summary.withinSlo).toBe(p95.measuredMs! <= p95.targetMs);
    expect(summary.costMicrousd).toBe(totals(OPERATIONS).totalMicrousd);
    expect(summary.pendingApprovals).toBe(WALL.matches.reduce((n, m) => n + m.pendingApprovals, 0));
    expect(summary.corrections).toBe(WALL.matches.reduce((n, m) => n + m.corrections, 0));
    expect(summary.liveMatches).toBe(0);
  });

  it("keeps the latest items newest first and the latest correction as the desk reported it", () => {
    const room = controlRoom(WALL, OPERATIONS);

    expect(room.activity.map((a) => a.text)).toEqual(WALL.activity.map((a) => a.headline));
    const latest = WALL.latestCorrection!;
    expect(room.latestCorrection).toMatchObject({
      reason: latest.summary,
      published: latest.outText,
      corrected: latest.inText,
      itemsCorrected: latest.itemsCorrected,
    });
  });

  it("shows matches not yet started with no clock, no latency and no throughput", () => {
    const idle: MatchdayWall = {
      ...WALL,
      activity: [],
      latestCorrection: null,
      matches: WALL.matches.map((m) => ({
        ...m,
        state: "idle",
        clock: null,
        score: { home: 0, away: 0 },
        items: 0,
        pendingApprovals: 0,
        corrections: 0,
        onAir: [],
      })),
    };

    const room = controlRoom(idle, null);

    expect(room.matches.every((m) => m.status === "not_started" && m.clock === null)).toBe(true);
    expect(room.matches.every((m) => m.p95LatencyMs === null && m.itemsPerMinute === null)).toBe(
      true,
    );
    expect(room.summary.p95LatencyMs).toBeNull();
    // Unknown, not free: operations could not be read.
    expect(room.summary.costMicrousd).toBeNull();
  });

  it("leaves out a partner the studio does not know, rather than mislabel it", () => {
    const stranger: MatchdayWall = {
      ...WALL,
      matches: WALL.matches.map((m) => ({ ...m, state: "running", onAir: ["harbour-tv"] })),
      activity: [{ ...WALL.activity[0]!, tenantId: "harbour-tv" }, ...WALL.activity.slice(1)],
    } as unknown as MatchdayWall;

    const room = controlRoom(stranger, OPERATIONS);

    expect(room.matches.every((m) => m.onAir.length === 0)).toBe(true);
    expect(room.activity).toHaveLength(WALL.activity.length - 1);
  });
});
