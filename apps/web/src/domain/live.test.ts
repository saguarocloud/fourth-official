import { describe, expect, it } from "vitest";

import type { FeedEntry, TenantItemEntry } from "@/contracts/feed";
import feedM42Partners from "@/fixtures/feed-m42-partners.json";
import feedM42 from "@/fixtures/feed-m42.json";

import { applyEntry, emptyLive, foldFeed, itemState, liveVerdict, parseEntry } from "./live";

const FEED = feedM42 as unknown as FeedEntry[];
const PARTNER_FEED = feedM42Partners as unknown as FeedEntry[];

describe("foldFeed", () => {
  const live = foldFeed(FEED);

  it("keeps the latest clock and score", () => {
    expect(live.clock?.score).toEqual({ home: 2, away: 1 });
    expect(live.clock?.clock.period).toBe(2);
  });

  it("lists every moment once, newest first, each with its insight", () => {
    const minutes = live.items.map((item) => item.moment.asOfSeq);
    expect(minutes).toEqual([...minutes].sort((a, b) => b - a));
    expect(live.items).toHaveLength(7);
    expect(live.items.every((item) => item.insight !== null)).toBe(true);
  });

  it("retracts the insight about a goal that VAR ruled out, but not the overturn itself", () => {
    const voided = live.items.find(
      (item) => item.moment.kind === "goal" && item.moment.clock.minute === 67,
    );
    const overturn = live.items.find((item) => item.moment.kind === "var_overturn");

    expect(voided && itemState(voided)).toBe("retracted");
    expect(voided?.correction?.summary).toBe("Harbour City goal at 67' ruled out for offside");
    expect(overturn && itemState(overturn)).toBe("published");
  });

  it("amends the insight whose scorer was reassigned", () => {
    const winner = live.items.find(
      (item) => item.moment.kind === "goal" && item.moment.clock.minute === 89,
    );

    expect(winner && itemState(winner)).toBe("amended");
    expect(winner?.correction?.summary).toMatch(/^Harbour City goal at 89' credited to /);
  });

  it("keeps every correction, latest last", () => {
    expect(live.corrections.map((c) => c.correction.kind)).toEqual([
      "EVENT_VOIDED",
      "EVENT_AMENDED",
    ]);
  });
});

describe("applyEntry", () => {
  it("never applies an entry twice or out of order", () => {
    const once = FEED.slice(0, 20).reduce(applyEntry, emptyLive(1));
    const twice = FEED.slice(0, 20).reduce(applyEntry, once);

    expect(twice).toEqual(once);
  });

  it("shows a moment as being drafted until its insight arrives", () => {
    const moment = FEED.findIndex((entry) => entry.kind === "moment");
    const live = FEED.slice(0, moment + 1).reduce(applyEntry, emptyLive(1));

    const [newest] = live.items;
    expect(newest && itemState(newest)).toBe("drafting");
  });
});

describe("parseEntry", () => {
  it("accepts a feed entry for the match it was asked for", () => {
    expect(parseEntry(JSON.stringify(FEED[0]), "m42")).toEqual(FEED[0]);
  });

  it.each([
    ["not json", "{"],
    ["another match", JSON.stringify({ ...FEED[0], matchId: "m43" })],
    ["an unknown kind", JSON.stringify({ ...FEED[0], kind: "gossip" })],
    ["no number", JSON.stringify({ ...FEED[0], entrySeq: "1" })],
    ["not an object", "[1, 2]"],
  ])("refuses %s", (_, raw) => {
    expect(parseEntry(raw, "m42")).toBeNull();
  });
});

describe("parseEntry, for a partner's item", () => {
  const item = PARTNER_FEED.find((e) => e.kind === "tenant_item")!;
  const overlay = (item as TenantItemEntry).overlay;

  it("accepts a well-formed one", () => {
    expect(parseEntry(JSON.stringify(item), "m42")).toEqual(item);
  });

  it.each([
    ["no partner", { ...item, tenantId: 7 }],
    ["no overlay", { ...item, overlay: null }],
    ["no item id", { ...item, overlay: { ...overlay, itemId: undefined } }],
    ["no content", { ...item, overlay: { ...overlay, content: "x" } }],
    ["no template", { ...item, overlay: { ...overlay, content: {} } }],
    ["a broken in time", { ...item, overlay: { ...overlay, inAt: { minute: "1" } } }],
    ["no out time", { ...item, overlay: { ...overlay, outAt: undefined } }],
  ])("refuses one with %s", (_, entry) => {
    expect(parseEntry(JSON.stringify(entry), "m42")).toBeNull();
  });
});

describe("liveVerdict", () => {
  it("says when nothing is playing", () => {
    expect(liveVerdict(emptyLive(0), "idle")).toEqual({
      tone: "amber",
      text: "No replay is running. Start the matchday to watch it unfold.",
    });
  });

  it("summarises a match under way", () => {
    expect(liveVerdict(foldFeed(FEED.slice(0, 40)), "running").tone).toBe("green");
  });

  it("counts corrections once the match is over", () => {
    expect(liveVerdict(foldFeed(FEED), "finished")).toEqual({
      tone: "green",
      text: "Full time. 7 verified insights; 2 corrections reached every item they touched.",
    });
  });

  it("raises a failed replay", () => {
    expect(liveVerdict(emptyLive(1), "failed").tone).toBe("red");
  });
});

describe("partner items", () => {
  it("are not Match Live's to show: they only move the feed on", () => {
    const live = foldFeed(FEED.slice(0, 10));
    const partnerItem = { kind: "tenant_item", entrySeq: live.lastSeq + 1 } as unknown as FeedEntry;

    const next = applyEntry(live, partnerItem);

    expect(next.lastSeq).toBe(live.lastSeq + 1);
    expect(next.items).toBe(live.items);
    expect(next.corrections).toBe(live.corrections);
  });
});
