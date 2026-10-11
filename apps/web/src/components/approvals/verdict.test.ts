import { describe, expect, it } from "vitest";

import type { TenantItemEntry } from "@/contracts/feed";
import { foldBroadcast } from "@/domain/broadcast";
import { waiting } from "@/domain/approvals";
import { FEED } from "@/components/broadcast/testing";

import { approvalsVerdict } from "./verdict";

const HELD: readonly TenantItemEntry[] = waiting(foldBroadcast(FEED));
const base = { waiting: HELD, decided: 0 };

describe("approvalsVerdict", () => {
  it("says what waits, and since when, while the match runs", () => {
    expect(approvalsVerdict({ ...base, phase: "running" })).toEqual({
      tone: "amber",
      text: `${HELD.length} items wait for an editor; the oldest since ${"68'"}.`,
    });
    expect(approvalsVerdict({ ...base, waiting: HELD.slice(0, 1), phase: "running" }).text).toMatch(
      /^1 item waits/,
    );
  });

  it("speaks of full time only once the match is over", () => {
    expect(approvalsVerdict({ ...base, phase: "finished" }).text).toBe(
      `Full time. ${HELD.length} held items stayed off air.`,
    );
    expect(approvalsVerdict({ waiting: [], decided: 2, phase: "finished" }).text).toBe(
      "Full time. Nothing waits for an editor; 2 decisions this match.",
    );
    expect(approvalsVerdict({ ...base, phase: "idle" }).text).toBe(
      "This match has not started. Start the matchday from Match Live.",
    );
    expect(approvalsVerdict({ ...base, phase: "failed" }).text).toBe(
      "This match's replay stopped. Held items stay off air.",
    );
  });

  it("says when nothing waits, the matchday is loading, or the service is down", () => {
    expect(approvalsVerdict({ waiting: [], decided: 1, phase: "running" })).toEqual({
      tone: "green",
      text: "Nothing waits for an editor. 1 decision this match.",
    });
    expect(approvalsVerdict({ waiting: [], decided: 0, phase: "running" }).tone).toBe("neutral");
    expect(approvalsVerdict({ ...base, phase: "loading" }).text).toBe("Loading the matchday.");
    expect(approvalsVerdict({ ...base, phase: "unavailable" }).tone).toBe("red");
  });
});
