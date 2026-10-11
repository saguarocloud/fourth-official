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

  it("opens on the latest correction, with its board, summary and every item it reached", async () => {
    await played();

    expect(
      screen.getByRole("heading", { level: 2, name: /credited to Idris Briceño/ }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Out: HCY 19")).toBeInTheDocument();
    // Tribuna's version was held, never published: the board counts what went out.
    expect(screen.getByText("2 published items corrected.")).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Impact" });
    expect(summary).toHaveTextContent("3 items · 3 partners · 3 languages");
    const boards = within(screen.getByRole("list", { name: "Items corrected" })).getAllByRole(
      "listitem",
    );
    expect(boards).toHaveLength(3);
    expect(boards[0]).toHaveTextContent("Northlight Sport");
    expect(boards[0]).toHaveTextContent("Amended");
    expect(boards[2]).toHaveTextContent("Pulled off air");
  });

  it("shows what went out and what came in, in each partner's language", async () => {
    await played();
    const [northlight, rheinblick] = within(
      screen.getByRole("list", { name: "Items corrected" }),
    ).getAllByRole("listitem");

    expect(within(northlight!).getByRole("group", { name: "Out" })).toHaveTextContent(
      "Niklas Navarro-Gil",
    );
    expect(within(northlight!).getByRole("group", { name: "In" })).toHaveTextContent(
      "Idris Briceño",
    );
    expect(
      within(rheinblick!).getByRole("group", { name: "In" }).querySelector("[lang='de-DE']"),
    ).not.toBeNull();
  });

  it("switches to another correction from its key", async () => {
    await played();

    fireEvent.click(screen.getByRole("button", { name: /^Ruled out/ }));

    expect(
      screen.getByRole("heading", { level: 2, name: /ruled out for offside/ }),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("list", { name: "Items corrected" }))
        .getAllByRole("listitem")
        .every((b) => b.textContent?.includes("Pulled off air")),
    ).toBe(true);
  });

  it("draws the impact from the event to every partner, and replays it", async () => {
    await played();
    const strip = screen.getByRole("img", {
      name: /m42-e2044 reached 1 insight and 3 partner items/,
    });
    expect(strip.querySelectorAll("[data-node='item']")).toHaveLength(3);

    fireEvent.click(screen.getByRole("button", { name: /Replay/ }));
    expect(document.querySelector("[data-replay]")).not.toBeNull();
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
