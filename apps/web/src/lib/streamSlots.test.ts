import { describe, expect, it } from "vitest";

import { clientOf, streamSlots } from "./streamSlots";

describe("streamSlots", () => {
  it("gives each client a limited number of open streams", () => {
    const slots = streamSlots(2);
    const first = slots.claim("a");
    const second = slots.claim("a");

    expect(first).not.toBeNull();
    expect(second).not.toBeNull();
    expect(slots.claim("a")).toBeNull();
    expect(slots.claim("b")).not.toBeNull();

    first!();
    expect(slots.claim("a")).not.toBeNull();
  });

  it("releases a slot once, however often it is released", () => {
    const slots = streamSlots(1);
    const release = slots.claim("a")!;
    release();
    release();

    expect(slots.claim("a")).not.toBeNull();
    expect(slots.claim("a")).toBeNull();
  });
});

describe("clientOf", () => {
  const request = (headers: Record<string, string>) =>
    new Request("http://studio/api/matches/m42/stream", { headers });

  it("is the address the ingress appended, not one the client claimed", () => {
    expect(clientOf(request({ "x-forwarded-for": "6.6.6.6, 203.0.113.9" }))).toBe("203.0.113.9");
    expect(clientOf(request({ "x-forwarded-for": "203.0.113.9" }))).toBe("203.0.113.9");
  });

  it("counts an IPv6 client by its /64, as one subscriber is handed a whole /64", () => {
    const at = (address: string) => clientOf(request({ "x-forwarded-for": address }));

    expect(at("2001:db8:1:2:aaaa::1")).toBe("2001:db8:1:2::/64");
    expect(at("2001:db8:1:2:ffff:ffff:ffff:ffff")).toBe("2001:db8:1:2::/64");
    expect(at("2001:db8::7")).toBe("2001:db8:0:0::/64");
    expect(at("[2001:DB8:1:2::9]")).toBe("2001:db8:1:2::/64");
  });

  it("groups requests without a forwarded address together", () => {
    expect(clientOf(request({}))).toBe("direct");
  });
});
