import { describe, expect, it } from "vitest";

import { rateLimit } from "./rateLimit";

describe("rateLimit", () => {
  it("allows a client its share of a window, then says when to come back", () => {
    let now = 0;
    const limit = rateLimit({ perWindow: 2, windowMs: 60_000, now: () => now });

    expect(limit.take("a")).toBe(0);
    expect(limit.take("a")).toBe(0);
    expect(limit.take("a")).toBe(60);
    expect(limit.take("b")).toBe(0);
    now = 30_000;
    expect(limit.take("a")).toBe(30);
    now = 60_000;
    expect(limit.take("a")).toBe(0);
  });

  it("holds at most so many clients, and makes a newcomer wait when it is full", () => {
    let now = 0;
    const limit = rateLimit({ perWindow: 5, windowMs: 1000, maxClients: 3, now: () => now });
    for (const client of ["a", "b", "c"]) expect(limit.take(client)).toBe(0);

    expect(limit.take("d")).toBe(1);
    expect(limit.take("a")).toBe(0);
    expect(limit.size()).toBe(3);
    now = 1000;
    expect(limit.take("d")).toBe(0);
    expect(limit.size()).toBe(1);
  });

  it("forgets clients whose window has passed", () => {
    let now = 0;
    const limit = rateLimit({ perWindow: 1, windowMs: 1000, now: () => now });
    for (let i = 0; i < 50; i += 1) limit.take(`c${i}`);

    now = 2000;
    limit.take("fresh");
    expect(limit.size()).toBe(1);
  });
});
