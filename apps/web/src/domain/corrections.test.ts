import { describe, expect, it } from "vitest";

import type { FeedEntry } from "@/contracts/feed";
import feedM42 from "@/fixtures/feed-m42-partners.json";

import { foldBroadcast } from "./broadcast";
import { incidents } from "./corrections";

const FEED = feedM42 as unknown as FeedEntry[];
const DONE = foldBroadcast(FEED);

describe("incidents", () => {
  const [ruledOut, credited] = incidents(DONE);

  it("is one incident per correction, in the order they were issued", () => {
    expect(incidents(DONE).map((i) => i.correction.correction.correctionId)).toEqual([
      "c-m42-01",
      "c-m42-02",
    ]);
    expect(ruledOut!.correction.summary).toBe("Harbour City goal at 67' ruled out for offside");
  });

  it("merges every report of a correction: its actions, its insights and the time they took", () => {
    expect(credited!.changes.map((c) => [c.action.tenantId, c.action.action])).toEqual([
      ["northlight-sport", "amended"],
      ["rheinblick-sport", "amended"],
      ["tribuna-austral", "retracted"],
    ]);
    expect(credited!.insightIds).toEqual(["in-m42-goal-HCY-s2044-a1"]);
    expect(credited!.elapsedMs).toBe(6);
    expect(credited!.startedAt).toBe("2026-10-11T15:00:00.000Z");
  });

  it("shows what went out and what came in for every item", () => {
    const northlight = credited!.changes[0]!;
    expect(northlight.before?.state).toBe("on_air");
    expect(northlight.before?.overlay.version).toBe(1);
    expect(northlight.after?.overlay.version).toBe(2);
    expect(northlight.after?.overlay.supersedes).toBe(northlight.before?.overlay.itemId);

    const tribuna = ruledOut!.changes.find((c) => c.action.tenantId === "tribuna-austral")!;
    expect(tribuna.before?.state).toBe("pending_approval");
    expect(tribuna.after).toBeNull();
  });

  it("counts the items, partners and languages reached", () => {
    expect([ruledOut!.items, ruledOut!.partners, ruledOut!.languages]).toEqual([3, 3, 3]);
  });

  it("is nothing before any correction, and a correction with no report yet has no changes", () => {
    const first = FEED.findIndex((e) => e.kind === "correction");
    expect(incidents(foldBroadcast(FEED.slice(0, first)))).toEqual([]);
    const [pending] = incidents(foldBroadcast(FEED.slice(0, first + 1)));
    expect(pending!.changes).toEqual([]);
    expect(pending!.reports).toEqual([]);
  });
});
