import { describe, expect, it } from "vitest";

import type { FeedEntry, TenantItemEntry } from "@/contracts/feed";
import feedM42 from "@/fixtures/feed-m42-partners.json";

import { foldBroadcast } from "./broadcast";
import { correctedSince, decisions, englishVersion, latestVersions, waiting } from "./approvals";

const FEED = feedM42 as unknown as FeedEntry[];
const DONE = foldBroadcast(FEED);
const NEXT = Math.max(...FEED.map((e) => e.entrySeq)) + 1;

const held = () => DONE.items.filter((i) => i.state === "pending_approval");

function decided(item: TenantItemEntry, seq: number, decision: "approved" | "rejected") {
  return {
    ...item,
    entrySeq: seq,
    state: decision === "approved" ? "on_air" : "rejected",
    approval: {
      editor: "T. Ibarra",
      decidedAt: `2026-10-11T15:0${seq - NEXT}:00.000Z`,
      decision,
      ...(decision === "rejected" ? { reason: "Not our tone" } : {}),
    },
  } as TenantItemEntry;
}

describe("latestVersions", () => {
  it("keeps each partner's item once, as its latest version, where it first appeared", () => {
    const [first] = held();
    const later = decided(first!, NEXT, "approved");
    const versions = latestVersions(foldBroadcast([...FEED, later]));

    const mine = versions.filter((v) => v.overlay.itemId === first!.overlay.itemId);
    expect(mine).toEqual([later]);
    expect(versions).toHaveLength(DONE.items.length);
    expect(versions.indexOf(later)).toBe(DONE.items.indexOf(first!));
  });
});

describe("waiting", () => {
  it("lists the items held for an editor, oldest first", () => {
    const queue = waiting(DONE);

    expect(queue).toHaveLength(7);
    expect(queue.every((i) => i.state === "pending_approval")).toBe(true);
    expect(queue.map((i) => i.entrySeq)).toEqual(
      [...queue.map((i) => i.entrySeq)].sort((a, b) => a - b),
    );
  });

  it("drops an item once an editor decides on it", () => {
    const [first, second] = held();
    const state = foldBroadcast([
      ...FEED,
      decided(first!, NEXT, "approved"),
      decided(second!, NEXT + 1, "rejected"),
    ]);

    expect(waiting(state)).toHaveLength(5);
  });
});

describe("decisions", () => {
  it("lists what editors decided, newest first, with the reason for a rejection", () => {
    const [first, second] = held();
    const state = foldBroadcast([
      ...FEED,
      decided(first!, NEXT, "approved"),
      decided(second!, NEXT + 1, "rejected"),
    ]);

    const log = decisions(state);
    expect(log.map((i) => i.approval?.decision)).toEqual(["rejected", "approved"]);
    expect(log[0]?.approval?.reason).toBe("Not our tone");
    expect(decisions(DONE)).toEqual([]);
  });
});

describe("englishVersion", () => {
  it("is the English partner's words for the same insight", () => {
    const [spanish] = held();
    const english = englishVersion(DONE, spanish!);

    expect(english?.overlay.locale).toBe("en-GB");
    expect(english?.localized?.insightId).toBe(spanish!.localized?.insightId);
  });

  it("is nothing for an item already in English, or one no English partner received", () => {
    const english = DONE.items.find(
      (i) => i.overlay.locale === "en-GB" && i.itemKind === "insight",
    )!;
    const [spanish] = held();
    const alone = { ...DONE, items: DONE.items.filter((i) => i.overlay.locale !== "en-GB") };

    expect(englishVersion(DONE, english)).toBeNull();
    expect(englishVersion(alone, spanish!)).toBeNull();
  });
});

describe("correctedSince", () => {
  it("marks a held item whose evidence a correction targets, and only that", () => {
    const targets = new Set(DONE.corrections.map((c) => c.correction.targetEventId));
    const touched = held().filter((i) =>
      i.localized?.claims.some((c) => c.evidence.eventIds.some((id) => targets.has(id))),
    );

    expect(touched.length).toBeGreaterThan(0);
    expect(held().filter((i) => correctedSince(DONE, i))).toEqual(touched);
  });
});
