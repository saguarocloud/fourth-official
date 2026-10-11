import { describe, expect, it } from "vitest";

import { FEED } from "@/components/broadcast/testing";
import { foldBroadcast } from "@/domain/broadcast";
import { incidents } from "@/domain/corrections";

import { correctionsVerdict } from "./verdict";

const ALL = incidents(foldBroadcast(FEED));

describe("correctionsVerdict", () => {
  it("is amber, and says so, while a new version waits for an editor", () => {
    const escalated = ALL.map((i) => ({
      ...i,
      changes: i.changes.map((c) =>
        c.action.action === "amended"
          ? { ...c, action: { ...c.action, action: "escalated" as const } }
          : c,
      ),
    }));

    expect(correctionsVerdict(escalated, false, false)).toEqual({
      tone: "amber",
      text: "2 corrections this match: 6 partner items corrected across 3 partners and 3 languages; 2 new versions held for an editor.",
    });
  });

  it("says when the service is down or the matchday is loading", () => {
    expect(correctionsVerdict(ALL, true, false).tone).toBe("red");
    expect(correctionsVerdict([], false, true).text).toBe("Loading the matchday.");
  });
});
