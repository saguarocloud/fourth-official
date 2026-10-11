import { describe, expect, it } from "vitest";

import type { ClockEntry, FeedEntry, MatchClock, TenantItemEntry } from "@/contracts/feed";
import feedM42 from "@/fixtures/feed-m42-partners.json";

import {
  PARTNERS,
  applyBroadcast,
  emptyBroadcast,
  foldBroadcast,
  instant,
  onAir,
  phaseAt,
  preview,
  rundown,
} from "./broadcast";

const FEED = feedM42 as unknown as FeedEntry[];
const DONE = foldBroadcast(FEED);

function at(clock: ClockEntry, when: MatchClock): ClockEntry {
  return { ...clock, clock: when };
}

function itemsOf(kind: string): TenantItemEntry[] {
  return FEED.filter((e): e is TenantItemEntry => e.kind === "tenant_item" && e.itemKind === kind);
}

describe("the partners", () => {
  it("are the three broadcast partners, in key order", () => {
    expect(PARTNERS.map((p) => [p.id, p.locale, p.key])).toEqual([
      ["northlight-sport", "en-GB", "1"],
      ["tribuna-austral", "es-MX", "2"],
      ["rheinblick-sport", "de-DE", "3"],
    ]);
  });
});

describe("foldBroadcast", () => {
  it("keeps every partner item, the clock and the corrections", () => {
    expect(DONE.items).toHaveLength(FEED.filter((e) => e.kind === "tenant_item").length);
    expect(DONE.clock?.score).toEqual({ home: 2, away: 1 });
    expect(DONE.corrections).toHaveLength(2);
  });

  it("applies an entry once, however often the feed is replayed", () => {
    const twice = FEED.reduce(applyBroadcast, DONE);
    expect(twice).toEqual(DONE);
  });

  it("skips an entry older than the last one applied, as after a reconnect", () => {
    const half = foldBroadcast(FEED.slice(0, 60));
    expect(FEED.slice(0, 40).reduce(applyBroadcast, half)).toEqual(half);
  });
});

describe("rundown", () => {
  const rows = rundown(DONE);

  it("has a row per moment explained and per correction, newest first", () => {
    const insights = new Set(itemsOf("insight").map((i) => i.localized?.insightId));
    expect(rows.filter((r) => r.kind === "insight")).toHaveLength(insights.size);
    expect(rows.filter((r) => r.kind === "correction")).toHaveLength(2);
    const order = rows.map((r) => instant(r.at));
    expect(order).toEqual([...order].sort((a, b) => b - a));
  });

  it("shows each partner's version of the same moment side by side", () => {
    const goal = rows.find((r) => r.kind === "insight" && r.label === "Goal");
    expect(goal).toBeDefined();
    expect(Object.keys(goal!.byPartner).sort()).toEqual([
      "northlight-sport",
      "rheinblick-sport",
      "tribuna-austral",
    ]);
    expect(goal!.byPartner["tribuna-austral"]?.state).toBe("pending_approval");
    expect(goal!.byPartner["rheinblick-sport"]?.overlay.locale).toBe("de-DE");
  });

  it("names a correction by what changed", () => {
    const corrections = rows.filter((r) => r.kind === "correction").map((r) => r.title);
    expect(corrections).toContain("Harbour City goal at 67' ruled out for offside");
  });
});

describe("onAir", () => {
  it("is nothing before kick-off", () => {
    expect(onAir(emptyBroadcast(1), "northlight-sport")).toEqual({
      lowerThird: null,
      strap: null,
      score: null,
    });
  });

  it("keeps the latest score on the bug, and drops graphics whose time has passed", () => {
    const later = { ...DONE, clock: at(DONE.clock!, { period: 2, minute: 104, second: 0 }) };
    const now = onAir(later, "rheinblick-sport");

    expect(now.score?.overlay.content).toMatchObject({ score: "2:1" });
    expect(now.lowerThird).toBeNull();
    expect(now.strap).toBeNull();
  });

  it("puts a graphic on air from its in time to its out time, and never one held for approval", () => {
    const goal = itemsOf("insight").find((i) => i.tenantId === "rheinblick-sport")!;
    const held = itemsOf("insight").find((i) => i.tenantId === "tribuna-austral")!;
    const state = { ...DONE, items: [goal, held] };

    const during = { ...state, clock: at(DONE.clock!, goal.overlay.inAt) };
    const after = {
      ...state,
      clock: at(DONE.clock!, { ...goal.overlay.outAt, second: goal.overlay.outAt.second + 1 }),
    };

    expect(onAir(during, "rheinblick-sport").lowerThird).toBe(goal);
    expect(onAir(after, "rheinblick-sport").lowerThird).toBeNull();
    expect(
      onAir({ ...state, clock: at(DONE.clock!, held.overlay.inAt) }, "tribuna-austral").lowerThird,
    ).toBeNull();
  });
});

describe("onAir, across the whole match", () => {
  it("airs nothing that has not come in yet, and the score as it stood", () => {
    const goal = itemsOf("insight").find((i) => i.tenantId === "northlight-sport")!;
    const then = { ...DONE, clock: at(DONE.clock!, goal.overlay.inAt) };
    const now = onAir(then, "northlight-sport");
    const scores = itemsOf("score").filter(
      (i) =>
        i.tenantId === "northlight-sport" && instant(i.overlay.inAt) <= instant(goal.overlay.inAt),
    );

    expect(now.lowerThird).toBe(goal);
    // The 67' goal's correction is on air; the 89' one has not come in yet.
    expect(now.strap?.overlay.content).toMatchObject({ text: expect.stringContaining("67'") });
    expect(now.score).toBe(scores.at(-1));
  });
});

describe("rundown, for corrections", () => {
  it("knows a correction's row before the correction itself arrives", () => {
    const early = { ...DONE, corrections: [] };
    const row = rundown(early).find(
      (r) => r.key === rundown(DONE).find((d) => d.kind === "correction")!.key,
    )!;

    expect(row.kind).toBe("correction");
    expect(row.label).toBe("Correction");
    expect(row.momentKind).toBeNull();
    expect(row.title).toMatch(/^CORRECTION: /);
  });

  it("leaves out an item whose id is not its partner's", () => {
    const stray = itemsOf("correction")[0]!;
    const foreign = { ...stray, overlay: { ...stray.overlay, itemId: "it-elsewhere-c-m42-01" } };

    expect(rundown({ ...DONE, items: [foreign] })).toEqual([]);
  });
});

describe("phaseAt", () => {
  const goal = itemsOf("insight").find((i) => i.tenantId === "northlight-sport")!;
  const held = itemsOf("insight").find((i) => i.tenantId === "tribuna-austral")!;

  it("tells a graphic waiting to come in from one on air and one that has aired", () => {
    expect(phaseAt(goal, instant(goal.overlay.inAt) - 1)).toBe("queued");
    expect(phaseAt(goal, instant(goal.overlay.inAt))).toBe("airing");
    expect(phaseAt(goal, instant(goal.overlay.outAt))).toBe("airing");
    expect(phaseAt(goal, instant(goal.overlay.outAt) + 1)).toBe("aired");
    expect(phaseAt(goal, null)).toBe("airing");
  });

  it("never airs a graphic held for approval", () => {
    expect(phaseAt(held, instant(held.overlay.inAt))).toBe("held");
  });
});

describe("rundown rows", () => {
  it("carry the moment's kind, and none for a correction", () => {
    const rows = rundown(DONE);

    expect(rows.find((r) => r.kind === "insight")?.momentKind).toBeTruthy();
    expect(rows.find((r) => r.kind === "correction")?.momentKind).toBeNull();
  });
});

describe("preview", () => {
  it("shows a partner's version of a chosen row, whatever its state", () => {
    const row = rundown(DONE).find((r) => r.kind === "insight")!;
    const shown = preview(DONE, "tribuna-austral", row.key);

    expect(shown.lowerThird?.tenantId).toBe("tribuna-austral");
    expect(shown.lowerThird?.state).toBe("pending_approval");
    expect(shown.score).not.toBeNull();
  });

  it("shows a correction's strap when a correction row is chosen", () => {
    const row = rundown(DONE).find((r) => r.kind === "correction")!;

    expect(preview(DONE, "northlight-sport", row.key).strap?.overlay.content).toMatchObject({
      template: "correction_strap",
    });
  });
});
