import { afterEach, describe, expect, it, vi } from "vitest";

import { sendDecision } from "./sendDecision";

const TARGET = { tenantId: "tribuna-austral", matchId: "m42", itemId: "it-tribuna-austral-x-v1" };

function answer(status: number, body: unknown = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(Response.json(body, { status }))),
  );
}

describe("sendDecision", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts to this app's own route, naming itself, with the run", async () => {
    const fetch = vi.fn(() => Promise.resolve(Response.json({ state: "on_air" })));
    vi.stubGlobal("fetch", fetch);

    expect(await sendDecision(TARGET, { decision: "approved", generation: 2 })).toEqual({
      ok: true,
    });
    expect(fetch).toHaveBeenCalledWith(
      "/api/tenants/tribuna-austral/matches/m42/items/it-tribuna-austral-x-v1/decision",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Requested-By": "fourth-official" },
        body: JSON.stringify({ decision: "approved", generation: 2 }),
        cache: "no-store",
      },
    );
  });

  it.each([
    [
      409,
      { detail: "this item is not awaiting a decision" },
      "This item is not awaiting a decision.",
    ],
    [
      410,
      { detail: "the match has reached full time; held items stay off air" },
      "The match has reached full time; held items stay off air.",
    ],
    [
      503,
      { detail: "no room on air this minute; try again shortly" },
      "No room on air this minute; try again shortly.",
    ],
    [404, {}, "That item is no longer on the feed. Reload to see the current run."],
    [422, {}, "That decision could not be sent. Check the reason and try again."],
    [502, {}, "The match service is unavailable. Try again shortly."],
  ])("says why a %i was refused", async (status, body, message) => {
    answer(status, body);

    expect(await sendDecision(TARGET, { decision: "approved", generation: 1 })).toEqual({
      ok: false,
      message,
    });
  });

  it("says so when the network fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("offline"))),
    );

    expect(await sendDecision(TARGET, { decision: "approved", generation: 1 })).toEqual({
      ok: false,
      message: "The match service is unavailable. Try again shortly.",
    });
  });
});
