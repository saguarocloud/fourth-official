import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DEMO_MATCHDAY } from "@/fixtures/matchday";
import type { Match } from "@/domain/matchday";

import { MatchBoard } from "./MatchBoard";

const featured = DEMO_MATCHDAY.matches.find((m) => m.featured)!;

function renderBoard(match: Match = featured) {
  return render(<MatchBoard match={match} partners={DEMO_MATCHDAY.partners} sloMs={8000} />);
}

describe("MatchBoard", () => {
  it("summarises the fixture, score and minute in one accessible heading", () => {
    renderBoard({ ...featured, home: "HCY", away: "NGT", homeScore: 1, awayScore: 0, minute: 68 });

    expect(
      screen.getByRole("heading", { name: "Harbour City 1, Northgate FC 0, 68'" }),
    ).toBeInTheDocument();
  });

  it("shows each partner's on-air tally", () => {
    renderBoard({
      ...featured,
      onAir: { northlight: true, "tribuna-austral": false, rheinblick: false },
    });

    expect(screen.getByRole("status", { name: "Northlight Sport: on air" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Rheinblick Sport: off air" })).toBeInTheDocument();
  });

  it("lists the match's publishing activity", () => {
    renderBoard({ ...featured, itemsPerMinute: 3.5, pendingApprovals: 2, corrections: 1 });
    const stats = screen.getByRole("list", { name: "Publishing activity" });

    expect(within(stats).getByText("3.5")).toBeInTheDocument();
    expect(within(stats).getByText("Pending approvals")).toBeInTheDocument();
  });

  it("flags latency outside the SLO in words", () => {
    renderBoard({ ...featured, p95LatencyMs: 9200 });

    expect(screen.getByText(/outside SLO/)).toBeInTheDocument();
  });
});
