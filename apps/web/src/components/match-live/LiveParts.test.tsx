import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { emptyLive } from "@/domain/live";

import { LiveScoreboard } from "./LiveScoreboard";
import { LiveWire } from "./LiveWire";
import { MatchSwitcher } from "./MatchSwitcher";
import { LIVE, MATCHES } from "./testing";

const NAMES = MATCHES[0]!;

describe("LiveScoreboard", () => {
  it("names the score, minute and state for screen readers", () => {
    render(<LiveScoreboard names={NAMES} clock={LIVE.clock} state="finished" />);

    expect(
      screen.getByRole("heading", { name: "Harbour City 2, Northgate FC 1, 90+3'" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Match clock 93:00" })).toBeInTheDocument();
    expect(screen.getByText("Full time")).toBeInTheDocument();
  });

  it("shows nil-nil at kick-off before any clock arrives", () => {
    render(<LiveScoreboard names={NAMES} clock={null} state="idle" />);

    expect(
      screen.getByRole("heading", { name: "Harbour City 0, Northgate FC 0" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Not started")).toBeInTheDocument();
  });
});

describe("LiveWire", () => {
  it("lists every moment, newest first", () => {
    render(<LiveWire live={LIVE} connection="ended" state="finished" />);

    const log = screen.getByRole("log", { name: "Verified moments" });
    expect(log.querySelectorAll(".wire-item")).toHaveLength(7);
    expect(log.querySelector(".wire-item__minute")).toHaveTextContent("89'");
  });

  it("shows placeholders while connecting", () => {
    const { container } = render(
      <LiveWire live={emptyLive(0)} connection="connecting" state="running" />,
    );
    expect(container.querySelectorAll(".wire-item--skeleton")).toHaveLength(3);
  });

  it.each([
    ["idle", /Start the matchday/],
    ["running", /first verified moment/],
  ] as const)("explains an empty wire when %s", (state, text) => {
    render(<LiveWire live={emptyLive(0)} connection="live" state={state} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("says so while reconnecting", () => {
    render(<LiveWire live={LIVE} connection="reconnecting" state="running" />);
    expect(screen.getByRole("status")).toHaveTextContent(/Reconnecting/);
  });
});

describe("MatchSwitcher", () => {
  it("links each match and marks the current one", () => {
    render(
      <MatchSwitcher
        matches={[...MATCHES, { ...MATCHES[1]!, matchId: "m44", state: "running" }]}
        current="m42"
      />,
    );

    const current = screen.getByRole("link", { current: "page" });
    expect(current).toHaveAttribute("href", "/match?match=m42");
    expect(current).toHaveTextContent("FT");
    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });
});
