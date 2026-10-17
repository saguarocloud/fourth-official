import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TopBar } from "./TopBar";

const summary = {
  liveMatches: 3,
  pendingApprovals: 2,
  corrections: 1,
  p95LatencyMs: 4100,
  sloMs: 8000,
  withinSlo: true,
  costMicrousd: 18_420,
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

  it("does not claim an SLO state before anything has aired", () => {
    render(
      <TopBar
        summary={{ ...summary, liveMatches: 0, p95LatencyMs: null }}
        studio="S"
        replay={false}
      />,
    );

    expect(screen.getByText("Nothing aired yet")).toBeInTheDocument();
    expect(screen.queryByText("Within SLO")).toBeNull();
  });

  it("shows the cost so far, measured, to the hundredth of a cent", () => {
    render(<TopBar summary={summary} studio="S" replay={false} />);

    expect(screen.getByText("$0.0184")).toBeInTheDocument();
  });
});
