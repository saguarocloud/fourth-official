import { describe, expect, it } from "vitest";

import { foldBroadcast } from "@/domain/broadcast";

import { FEED } from "./testing";
import { verdictFor } from "./verdict";

const DONE = foldBroadcast(FEED);

describe("verdictFor", () => {
  it("counts each partner's item as it stands, held items by partner, and what corrections pulled", () => {
    expect(verdictFor(DONE, false, "finished")).toEqual({
      tone: "amber",
      text: "7 moments in three voices: 12 graphics cleared for air, 5 pending approval at Tribuna Austral; 4 pulled by corrections.",
    });
  });

  it("counts the partners holding items when there are several", () => {
    const items = DONE.items.map((i) =>
      i.tenantId === "rheinblick-sport" && i.itemKind === "insight" && i.state === "on_air"
        ? { ...i, state: "pending_approval" as const }
        : i,
    );

    expect(verdictFor({ ...DONE, items }, false, "finished").text).toMatch(
      /11 pending approval across 2 partners; 4 pulled by corrections\.$/,
    );
  });

  it("is green when nothing waits for an editor", () => {
    const items = DONE.items.map((i) => ({ ...i, state: "on_air" as const }));

    expect(verdictFor({ ...DONE, items }, false, "finished")).toEqual({
      tone: "green",
      text: "7 moments in three voices: 23 graphics cleared for air; nothing waits for an editor.",
    });
  });
});
