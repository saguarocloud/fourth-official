import { describe, expect, it } from "vitest";

import { foldBroadcast } from "@/domain/broadcast";

import { FEED } from "./testing";
import { verdictFor } from "./verdict";

const DONE = foldBroadcast(FEED);

describe("verdictFor", () => {
  it("names the partner holding items when there is one", () => {
    expect(verdictFor(DONE, false, "finished").text).toMatch(
      /pending approval at Tribuna Austral\.$/,
    );
  });

  it("counts the partners holding items when there are several", () => {
    const items = DONE.items.map((i) =>
      i.tenantId === "rheinblick-sport" && i.itemKind === "insight"
        ? { ...i, state: "pending_approval" as const }
        : i,
    );

    expect(verdictFor({ ...DONE, items }, false, "finished").text).toMatch(
      /14 pending approval across 2 partners\.$/,
    );
  });

  it("is green when nothing waits for an editor", () => {
    const items = DONE.items.map((i) => ({ ...i, state: "on_air" as const }));

    expect(verdictFor({ ...DONE, items }, false, "finished")).toEqual({
      tone: "green",
      text: "7 moments in three voices: 21 graphics cleared for air; nothing waits for an editor.",
    });
  });
});
