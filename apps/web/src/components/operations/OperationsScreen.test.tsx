import { render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/operations" }));

import type { OperationsReport } from "@/contracts/operations";
import { dollars, totals, verdict } from "@/domain/operations";
import fixture from "@/fixtures/operations.json";

import { OperationsScreen } from "./OperationsScreen";

const REPORT = fixture as unknown as OperationsReport;
const MATCHES = {
  matches: [
    {
      matchId: "m42",
      home: "HCY",
      away: "NGT",
      homeName: "Harbour City",
      awayName: "Northgate FC",
      state: "finished",
      entries: 10,
    },
    {
      matchId: "m43",
      home: "KBA",
      away: "ASV",
      homeName: "Kingsbridge Athletic",
      awayName: "Ashford Vale",
      state: "finished",
      entries: 10,
    },
    {
      matchId: "m44",
      home: "CAL",
      away: "WMR",
      homeName: "Calder Town",
      awayName: "Westmere",
      state: "finished",
      entries: 10,
    },
  ],
};

function serve(report: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        url.startsWith("/api/matches") ? Response.json(MATCHES) : Response.json(report, { status }),
      ),
    ),
  );
}

const idle: OperationsReport = {
  ...REPORT,
  objectives: REPORT.objectives.map((o) => ({ ...o, measuredMs: null })),
  budget: { ...REPORT.budget, late: 0, of: 0 },
  onAir: { count: 0, p50Ms: null, p95Ms: null },
  matches: REPORT.matches.map((m) => ({
    ...m,
    state: "idle",
    runMs: 0,
    eventsPlayed: 0,
    moments: 0,
    explain: { count: 0, p50Ms: null, p95Ms: null },
    firstPass: { hit: 0, of: 0 },
    fallbacks: { hit: 0, of: 0 },
    modelDrafts: { hit: 0, of: 0 },
    modelErrors: 0,
    corrections: { count: 0, p50Ms: null, p95Ms: null },
    correctedItems: 0,
    tokens: { input: 0, output: 0 },
    modelCostMicrousd: 0,
    infraCostMicrousd: 0,
    partners: [],
  })),
};

describe("OperationsScreen", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("leads with the run's service levels, its error budget and its cost", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    expect(await screen.findByRole("status", { name: "Operations verdict" })).toHaveTextContent(
      verdict(REPORT).text,
    );
  });

  it("states every objective with its target and what was measured", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const levels = await screen.findByRole("table", { name: "Service levels" });
    const rows = within(levels).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Event to on air, median");
    expect(rows[0]).toHaveTextContent("4.0 s");
  });

  it("shows the amount on the board and what it is made of", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const sum = totals(REPORT);
    const amount = await screen.findByRole("region", { name: "Amount" });
    expect(within(amount).getByRole("img", { name: /^Cost/ })).toHaveAccessibleName(
      expect.stringContaining(dollars(sum.totalMicrousd)),
    );
    expect(amount).toHaveTextContent(dollars(sum.modelMicrousd));
    expect(amount).toHaveTextContent(dollars(sum.infraMicrousd));
  });

  it("itemises every match by name, with what it cost", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const table = await screen.findByRole("table", { name: "Itemised by match" });
    expect(await within(table).findByText("Harbour City v Northgate FC")).toBeInTheDocument();
    const [, body] = within(table).getAllByRole("rowgroup");
    const rows = within(body!).getAllByRole("row");
    expect(rows).toHaveLength(REPORT.matches.length);
    const m42 = REPORT.matches.find((m) => m.matchId === "m42")!;
    expect(rows[0]).toHaveTextContent(dollars(m42.modelCostMicrousd + m42.infraCostMicrousd));
  });

  it("totals each partner across the matches, against its own latency budget", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const table = await screen.findByRole("table", { name: "By partner" });
    const rheinblick = within(table).getByText("Rheinblick Sport").closest("tr")!;
    const theirs = REPORT.matches
      .flatMap((m) => m.partners)
      .filter((p) => p.tenantId === "rheinblick-sport");
    const within8 = theirs.reduce((n, p) => n + p.withinBudget.hit, 0);
    const timed = theirs.reduce((n, p) => n + p.withinBudget.of, 0);
    expect(rheinblick).toHaveTextContent(`${within8} of ${timed}`);
    expect(rheinblick).toHaveTextContent("8.0 s");
  });

  it("names the rates its costs were computed with", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const rates = await screen.findByRole("table", { name: "Rates" });
    expect(rates).toHaveTextContent("fast");
    expect(rates).toHaveTextContent("$0.25");
    expect(rates).toHaveTextContent("$2.00");
  });

  it("says nothing has been measured before a matchday runs", async () => {
    serve(idle);
    render(<OperationsScreen />);

    expect(await screen.findByRole("status", { name: "Operations verdict" })).toHaveTextContent(
      "Nothing measured yet",
    );
    const levels = screen.getByRole("table", { name: "Service levels" });
    expect(within(levels).getAllByText("Not yet measured")).toHaveLength(3);
  });

  it("says so when the report cannot be read", async () => {
    serve({ detail: "x" }, 502);
    render(<OperationsScreen />);

    expect(await screen.findByRole("status", { name: "Operations verdict" })).toHaveTextContent(
      "did not answer",
    );
  });

  it("has no accessibility violations", async () => {
    serve(REPORT);
    const { container } = render(<OperationsScreen />);
    await screen.findByRole("table", { name: "Itemised by match" });

    expect((await axe.run(container)).violations).toEqual([]);
  });

  it("says how far over an overspent budget went, on the meter and in words", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const meter = await screen.findByRole("meter", { name: "Error budget spent" });
    expect(meter).toHaveAttribute("aria-valuemax", "100");
    expect(meter).toHaveAttribute("aria-valuenow", "100");
    expect(meter.getAttribute("aria-valuetext")).toMatch(/times over/);
    expect(screen.getByText(/^Error budget spent [0-9.]+ times over$/)).toBeInTheDocument();
  });

  it("totals the itemised matches to the amount on the board", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const table = await screen.findByRole("table", { name: "Itemised by match" });
    const total = within(table).getByRole("row", { name: /^Total/ });
    expect(total).toHaveTextContent(dollars(totals(REPORT).totalMicrousd));
  });

  it("names a partner's cost for what it is, and its held items for what they are", async () => {
    serve(REPORT);
    render(<OperationsScreen />);

    const table = await screen.findByRole("table", { name: "By partner" });
    expect(within(table).getByRole("columnheader", { name: "Localizer cost" })).toBeInTheDocument();
    const tribuna = within(table).getByText("Tribuna Austral").closest("tr")!;
    expect(tribuna).toHaveTextContent("All held");
  });

  it("lists a partner the screen does not know by its id", async () => {
    const stranger = {
      ...REPORT,
      matches: REPORT.matches.map((m) => ({
        ...m,
        partners: m.partners.map((p) =>
          p.tenantId === "northlight-sport" ? { ...p, tenantId: "harbour-tv" } : p,
        ),
      })),
    };
    serve(stranger);
    render(<OperationsScreen />);

    const table = await screen.findByRole("table", { name: "By partner" });
    expect(within(table).getByText("harbour-tv")).toBeInTheDocument();
  });

  it("does not light a red lamp when the service is unreachable: nothing was missed", async () => {
    serve({ detail: "x" }, 502);
    render(<OperationsScreen />);

    const status = await screen.findByRole("status", { name: "Operations verdict" });
    await waitFor(() => expect(status).toHaveTextContent("did not answer"));
    expect(status).toHaveAttribute("data-tone", "neutral");
  });

  it("does not announce the running cost on every reading", async () => {
    serve({
      ...REPORT,
      matches: REPORT.matches.map((m) => ({ ...m, state: "running" })),
    });
    render(<OperationsScreen />);

    const status = await screen.findByRole("status", { name: "Operations verdict" });
    await waitFor(() => expect(status).toHaveTextContent("so far"));
    expect(status).toHaveAttribute("aria-live", "off");
  });

  it("dates the figures it keeps on show when a reading fails", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetch = vi
      .fn()
      .mockImplementation((url: string) =>
        Promise.resolve(
          url.startsWith("/api/matches") ? Response.json(MATCHES) : Response.json(REPORT),
        ),
      );
    vi.stubGlobal("fetch", fetch);
    render(<OperationsScreen />);
    await screen.findByRole("table", { name: "Itemised by match" });
    fetch.mockImplementation((url: string) =>
      url.startsWith("/api/matches")
        ? Promise.resolve(Response.json(MATCHES))
        : Promise.reject(new TypeError("offline")),
    );

    await vi.advanceTimersByTimeAsync(5000);

    expect(
      await screen.findByText(
        `The last reading failed: these are the figures as read at ${REPORT.generatedAt.slice(11, 19)} UTC.`,
      ),
    ).toBeInTheDocument();
    vi.useRealTimers();
  });
});
