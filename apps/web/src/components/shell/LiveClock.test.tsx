import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveClock, formatStudioTime } from "./LiveClock";

describe("formatStudioTime", () => {
  it("shows 24-hour London time, as the studio works in", () => {
    expect(formatStudioTime(new Date("2026-10-24T14:07:09Z"))).toBe("15:07:09");
  });
});

describe("LiveClock", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-24T14:07:09Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("ticks every second", () => {
    render(<LiveClock />);
    expect(screen.getByRole("img", { name: "Studio time 15:07:09" })).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByRole("img", { name: "Studio time 15:07:10" })).toBeInTheDocument();
  });
});

describe("LiveClock alignment", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("ticks on the wall-clock second, not a second after mount", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-24T14:07:09.600Z"));
    render(<LiveClock />);

    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(screen.getByRole("img", { name: "Studio time 15:07:10" })).toBeInTheDocument();
  });
});

describe("LiveClock lifecycle", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("stops ticking when unmounted", () => {
    vi.useFakeTimers();
    const { unmount } = render(<LiveClock />);
    unmount();

    expect(vi.getTimerCount()).toBe(0);
  });
});
