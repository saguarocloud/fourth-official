import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { OperationsReport } from "@/contracts/operations";
import type { MatchdayWall } from "@/contracts/wall";
import { PARTNERS } from "@/domain/broadcast";
import { controlRoom } from "@/domain/controlRoom";
import operations from "@/fixtures/operations.json";
import wall from "@/fixtures/wall.json";

const ROOM = controlRoom(
  wall as unknown as MatchdayWall,
  operations as unknown as OperationsReport,
);
import type { Match } from "@/domain/matchday";

import { MatchBoard } from "./MatchBoard";

const featured = ROOM.matches.find((m) => m.featured)!;

function renderBoard(match: Match = featured) {
  return render(<MatchBoard match={match} partners={PARTNERS} sloMs={8000} />);
}

describe("MatchBoard", () => {
  it("summarises the fixture, score and minute in one accessible heading", () => {
    renderBoard({
      ...featured,
      home: "HCY",
      away: "NGT",
      homeScore: 1,
      awayScore: 0,
      clock: { period: 2, minute: 68, second: 41 },
    });

    // 68:41 elapsed is the 69th minute, as broadcasters count it.
    expect(
      screen.getByRole("heading", { name: "Harbour City 1, Northgate FC 0, 69'" }),
    ).toBeInTheDocument();
  });

  it("shows each partner's on-air tally", () => {
    renderBoard({
      ...featured,
      onAir: ["northlight-sport"],
    });

    expect(screen.getByRole("img", { name: "Northlight Sport: on air" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Rheinblick Sport: off air" })).toBeInTheDocument();
  });

  it("lists the match's publishing activity", () => {
    renderBoard({ ...featured, itemsPerMinute: 3.5, pendingApprovals: 2, corrections: 1 });
    const stats = screen.getByRole("list", { name: "Publishing activity" });

    expect(within(stats).getByText("3.5")).toBeInTheDocument();
    expect(within(stats).getByText("Pending approvals")).toBeInTheDocument();
  });

  it("shows a match not started at zero, with nothing measured yet", () => {
    renderBoard({
      ...featured,
      clock: null,
      status: "not_started",
      itemsPerMinute: null,
      p95LatencyMs: null,
      onAir: [],
    });

    expect(screen.getByRole("img", { name: "Match clock 00:00" })).toBeInTheDocument();
    expect(screen.getByText("p95, nothing aired yet")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Not started$/ })).toBeInTheDocument();
  });

  it("flags latency outside the SLO in words", () => {
    renderBoard({ ...featured, p95LatencyMs: 9200 });

    expect(screen.getByText(/outside SLO/)).toBeInTheDocument();
  });
});
