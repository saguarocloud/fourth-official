import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TopBar } from "./TopBar";

const summary = {
  liveMatches: 3,
  itemsPerMinute: 7.5,
  pendingApprovals: 2,
  corrections: 1,
  p95LatencyMs: 4100,
  sloMs: 8000,
  withinSlo: true,
  costCents: 1842,
};

describe("TopBar", () => {
  it("names the product and the studio", () => {
    render(<TopBar summary={summary} studio="Meridian League Studios" replay />);

    expect(screen.getByText("Fourth Official")).toBeInTheDocument();
    expect(screen.getByText("Meridian League Studios")).toBeInTheDocument();
  });

  it("labels replayed synthetic data honestly", () => {
    render(<TopBar summary={summary} studio="Meridian League Studios" replay />);

    expect(screen.getByText("Replay of a synthetic matchday")).toBeInTheDocument();
  });

  it("states latency against the SLO in words", () => {
    render(
      <TopBar
        summary={{ ...summary, withinSlo: false, p95LatencyMs: 9100 }}
        studio="S"
        replay={false}
      />,
    );

    expect(screen.getByText("Outside SLO")).toBeInTheDocument();
  });

  it("does not claim an SLO state when nothing is live", () => {
    render(
      <TopBar
        summary={{ ...summary, liveMatches: 0, p95LatencyMs: null }}
        studio="S"
        replay={false}
      />,
    );

    expect(screen.getByText("No live matches")).toBeInTheDocument();
    expect(screen.queryByText("Within SLO")).toBeNull();
  });

  it("shows cost so far to the cent", () => {
    render(<TopBar summary={summary} studio="S" replay={false} />);

    expect(screen.getByText("US$18.42")).toBeInTheDocument();
  });
});
