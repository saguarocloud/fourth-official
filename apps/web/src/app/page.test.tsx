import { render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

import type { OperationsReport } from "@/contracts/operations";
import type { MatchdayWall } from "@/contracts/wall";
import { controlRoom } from "@/domain/controlRoom";
import { matchdayVerdict } from "@/domain/matchday";
import operations from "@/fixtures/operations.json";
import wall from "@/fixtures/wall.json";

import Home from "./page";

const WALL = wall as unknown as MatchdayWall;
const OPERATIONS = operations as unknown as OperationsReport;

function serve(answers: { wall?: Response; operations?: Response } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        url.startsWith("/api/wall")
          ? (answers.wall ?? Response.json(WALL))
          : (answers.operations ?? Response.json(OPERATIONS)),
      ),
    ),
  );
}

async function opened() {
  const view = render(<Home />);
  await screen.findAllByRole("article");
  return view;
}

describe("Control Room", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("leads with the screen name", async () => {
    serve();
    await opened();

    expect(screen.getByRole("heading", { level: 1, name: "Control Room" })).toBeInTheDocument();
  });

  it("gives a one-line verdict on the whole matchday, from what the platform measured", async () => {
    serve();
    await opened();

    const expected = matchdayVerdict(controlRoom(WALL, OPERATIONS).summary).text;
    expect(screen.getByRole("status", { name: "Matchday verdict" })).toHaveTextContent(expected);
  });

  it("shows every match on the wall", async () => {
    serve();
    await opened();

    expect(screen.getAllByRole("article")).toHaveLength(WALL.matches.length);
  });

  it("summarises the latest correction as out and in", async () => {
    serve();
    await opened();

    const latest = WALL.latestCorrection!;
    expect(screen.getByRole("img", { name: `Published ${latest.outText}` })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: `Corrected ${latest.inText}` })).toBeInTheDocument();
  });

  it("still shows the wall when operations cannot be read, without claiming latency", async () => {
    serve({ operations: Response.json({ detail: "x" }, { status: 502 }) });
    await opened();

    expect(screen.getAllByRole("article")).toHaveLength(WALL.matches.length);
    expect(screen.getAllByText("p95, nothing aired yet").length).toBeGreaterThan(0);
  });

  it("says so, without alarm, when the matchday service does not answer", async () => {
    serve({ wall: Response.json({ detail: "x" }, { status: 502 }) });
    render(<Home />);

    const verdict = await screen.findByRole("status", { name: "Matchday verdict" });
    await waitFor(() => expect(verdict).toHaveTextContent("did not answer"));
    expect(verdict).toHaveAttribute("data-tone", "neutral");
  });

  it("says when the wall on show is no longer current, and from when it is", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetch = vi.fn((url: string) =>
      Promise.resolve(
        url.startsWith("/api/wall") ? Response.json(WALL) : Response.json(OPERATIONS),
      ),
    );
    vi.stubGlobal("fetch", fetch);
    await opened();
    fetch.mockImplementation((url: string) =>
      url.startsWith("/api/wall")
        ? Promise.reject(new TypeError("offline"))
        : Promise.resolve(Response.json(OPERATIONS)),
    );

    await vi.advanceTimersByTimeAsync(5000);

    expect(
      await screen.findByText(
        `The last reading failed: this is the matchday as read at ${WALL.generatedAt.slice(11, 19)} UTC.`,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Matchday verdict" })).toHaveAttribute(
      "data-tone",
      "neutral",
    );
    vi.useRealTimers();
  });

  it("states that all data is synthetic and the league is fictional", async () => {
    serve();
    await opened();

    expect(
      screen.getByText(
        "All data is synthetic. The league, clubs, players and partners are fictional.",
      ),
    ).toBeInTheDocument();
  });

  it("offers a skip link to the main content", async () => {
    serve();
    await opened();

    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
  });
});

describe("Control Room accessibility", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("has no axe violations", async () => {
    serve();
    const { container } = await opened();

    // jsdom cannot compute colour contrast; contrast is checked against the token values instead.
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
