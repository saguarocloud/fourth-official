import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

import Home from "./page";

describe("Control Room", () => {
  it("leads with the screen name", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "Control Room" })).toBeInTheDocument();
  });

  it("gives a one-line verdict on the whole matchday", () => {
    render(<Home />);

    expect(screen.getByRole("status", { name: "Matchday verdict" })).toHaveTextContent(
      "All 3 matches under control. 3 items await approval.",
    );
  });

  it("shows every live match on the wall", () => {
    render(<Home />);

    expect(screen.getAllByRole("article")).toHaveLength(3);
  });

  it("summarises the latest correction as out and in", () => {
    render(<Home />);

    expect(screen.getByRole("img", { name: "Published 2-0" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Corrected 1-0" })).toBeInTheDocument();
  });

  it("states that all data is synthetic and the league is fictional", () => {
    render(<Home />);

    expect(
      screen.getByText(
        "All data is synthetic. The league, clubs, players and partners are fictional.",
      ),
    ).toBeInTheDocument();
  });

  it("offers a skip link to the main content", () => {
    render(<Home />);

    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
  });
});

describe("Control Room accessibility", () => {
  it("has no axe violations", async () => {
    const { container } = render(<Home />);

    // jsdom cannot compute colour contrast; contrast is checked against the token values instead.
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });

    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
