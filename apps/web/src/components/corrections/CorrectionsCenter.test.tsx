import { act, fireEvent, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/corrections",
  useSearchParams: () => search.value,
}));

import { FEED } from "@/components/broadcast/testing";
import { FakeEventSource, MATCHES } from "@/components/match-live/testing";

import { CorrectionsCenter } from "./CorrectionsCenter";

function serve(matches: unknown = MATCHES) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(Response.json({ matches }))),
  );
}

function stream(): FakeEventSource {
  const latest = FakeEventSource.instances.at(-1);
  if (latest === undefined) throw new Error("no stream");
  return latest;
}

async function played(feed = FEED) {
  serve();
  const view = render(<CorrectionsCenter />);
  await screen.findByText("Harbour City v Northgate FC · Meridian League");
  act(() => {
    stream().open();
    for (const entry of feed) stream().emit(entry.kind, entry);
  });
  return view;
}

describe("CorrectionsCenter", () => {
  beforeEach(() => {
    search.value = new URLSearchParams();
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("leads with what the corrections reached across the match", async () => {
    await played();

    expect(screen.getByRole("status", { name: "Corrections verdict" })).toHaveTextContent(
      "2 corrections this match: 6 partner items corrected across 3 partners and 3 languages.",
    );
  });

  it("opens on the correction that reached the most, with its board, summary and items", async () => {
    await played();

    expect(
      screen.getByRole("heading", { level: 2, name: /ruled out for offside/ }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Out: 2-0")).toBeInTheDocument();
    // The held version was never published: the board counts what was on air.
    expect(screen.getByText("2 published items corrected.")).toBeInTheDocument();
    expect(
      screen.getByText(/3 partner items \(2 on air, 1 held\) · 3 partners · 3 languages · \d+ ms/),
    ).toBeInTheDocument();
    const boards = within(screen.getByRole("list", { name: "Items corrected" })).getAllByRole(
      "listitem",
    );
    expect(boards).toHaveLength(3);
    expect(screen.getByRole("heading", { level: 3, name: "Northlight Sport" })).toBeInTheDocument();
    expect(boards.map((b) => within(b).getByRole("group", { name: /^In:/ }).textContent)).toEqual([
      "InPulled off air",
      "InPulled off air",
      "InWithdrawn before air",
    ]);
  });

  it("shows what went out and what came in, in each partner's language", async () => {
    await played();
    fireEvent.click(screen.getByRole("button", { name: /^Amended/ }));

    const out = screen.getByRole("group", { name: "Out: Northlight Sport" });
    const into = screen.getByRole("group", { name: "In: Northlight Sport" });
    expect(out).toHaveTextContent("Niklas Navarro-Gil");
    expect(out).toHaveTextContent("(replaced)");
    expect(into).toHaveTextContent("Idris Briceño");
    expect(
      screen.getByRole("group", { name: "In: Rheinblick Sport" }).querySelector("[lang='de-DE']"),
    ).not.toBeNull();
  });

  it("draws the impact in a producer's words, and replays it", async () => {
    await played();
    // Two layouts, wide and stacked for phones; CSS shows one (jsdom applies none).
    const strips = screen.getAllByRole("img", {
      name: "Harbour City goal at 67' ruled out for offside: reached 1 insight and 3 partner items",
    });
    expect(strips.map((s) => s.getAttribute("data-layout"))).toEqual(["narrow", "wide"]);
    for (const strip of strips) {
      expect(strip.querySelectorAll("[data-node='item']")).toHaveLength(3);
      expect(strip).toHaveTextContent("2-0 → 1-0");
      expect(strip).toHaveTextContent("Goal 67'");
      expect(strip).toHaveTextContent("Northlight Sport · en-GB");
    }

    fireEvent.click(screen.getByRole("button", { name: "Replay" }));
    expect(document.querySelector(".impact[data-replay]")).not.toBeNull();
    expect(screen.getByRole("heading", { level: 3, name: "Northlight Sport" })).toHaveFocus();
  });

  it("starts afresh on another match", async () => {
    const view = await played();
    fireEvent.click(screen.getByRole("button", { name: /^Amended/ }));

    search.value = new URLSearchParams("match=m43");
    view.rerender(<CorrectionsCenter />);
    await screen.findByText("Kingsbridge Athletic v Ashford Vale · Meridian League");
    search.value = new URLSearchParams("match=m42");
    view.rerender(<CorrectionsCenter />);
    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    act(() => {
      for (const entry of FEED) stream().emit(entry.kind, entry);
    });

    expect(
      screen.getByRole("heading", { level: 2, name: /ruled out for offside/ }),
    ).toBeInTheDocument();
  });

  it("says when a match has had no corrections", async () => {
    await played(FEED.filter((e) => e.kind !== "correction" && e.kind !== "correction_report"));

    expect(screen.getByRole("status", { name: "Corrections verdict" })).toHaveTextContent(
      "No corrections this match. When the source data changes, every item it reached appears here.",
    );
  });

  it("has no axe violations", async () => {
    const { container } = await played();

    // jsdom cannot compute colour contrast; contrast is checked against the token values instead.
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
