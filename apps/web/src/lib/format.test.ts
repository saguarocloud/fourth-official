import { describe, expect, it } from "vitest";

// Numbers and their units are joined by a non-breaking space so they never wrap apart.
const NBSP = "\u00a0";

import {
  formatCost,
  formatLatency,
  formatMatchClock,
  formatMatchMinute,
  formatPercent,
} from "./format";

describe("formatMatchClock", () => {
  it("pads minutes and seconds to mm:ss", () => {
    expect(formatMatchClock(5, 3)).toBe("05:03");
    expect(formatMatchClock(67, 12)).toBe("67:12");
  });

  it("keeps counting past ninety minutes", () => {
    expect(formatMatchClock(94, 59)).toBe("94:59");
  });

  it.each([
    [-1, 0],
    [10, 60],
    [Number.NaN, 0],
    [1.5, 0],
  ])("rejects an invalid clock %d:%d", (minute, second) => {
    expect(() => formatMatchClock(minute, second)).toThrow(RangeError);
  });
});

describe("formatMatchMinute", () => {
  it("shows regulation minutes plainly", () => {
    expect(formatMatchMinute(61, 2)).toBe("61'");
    expect(formatMatchMinute(45, 1)).toBe("45'");
  });

  it("shows added time after each half as base+extra", () => {
    expect(formatMatchMinute(47, 1)).toBe("45+2'");
    expect(formatMatchMinute(93, 2)).toBe("90+3'");
  });

  it("rejects a minute that cannot belong to the period", () => {
    expect(() => formatMatchMinute(30, 2)).toThrow(RangeError);
    expect(() => formatMatchMinute(0, 1)).toThrow(RangeError);
  });
});

describe("formatLatency", () => {
  it("shows seconds with one decimal in the viewer's locale", () => {
    expect(formatLatency(4120, "en-GB")).toBe(`4.1${NBSP}s`);
    expect(formatLatency(4120, "de-DE")).toBe(`4,1${NBSP}s`);
  });

  it("shows sub-second latency in milliseconds", () => {
    expect(formatLatency(480, "en-GB")).toBe(`480${NBSP}ms`);
  });

  it("rejects negative durations", () => {
    expect(() => formatLatency(-1, "en-GB")).toThrow(RangeError);
  });
});

describe("formatCost", () => {
  it("shows cents to the cent in USD", () => {
    expect(formatCost(42, "en-GB")).toBe("US$0.42");
    expect(formatCost(123456, "en-US")).toBe("$1,234.56");
  });

  it("uses the locale's separators", () => {
    expect(formatCost(123456, "de-DE")).toBe(`1.234,56${NBSP}$`);
  });

  it("rejects fractional or negative cents", () => {
    expect(() => formatCost(1.5, "en-GB")).toThrow(RangeError);
    expect(() => formatCost(-1, "en-GB")).toThrow(RangeError);
  });
});

describe("formatPercent", () => {
  it("formats a ratio as a whole percentage", () => {
    expect(formatPercent(0.587, "en-GB")).toBe("59%");
    expect(formatPercent(0.587, "de-DE")).toBe(`59${NBSP}%`);
  });

  it("rejects ratios outside 0..1", () => {
    expect(() => formatPercent(1.2, "en-GB")).toThrow(RangeError);
  });
});
