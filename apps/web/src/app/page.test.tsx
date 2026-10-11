import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("Home", () => {
  it("names the product in the main heading", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { level: 1, name: "Fourth Official" })).toBeInTheDocument();
  });

  it("states that all data is synthetic and the league is fictional", () => {
    render(<Home />);

    expect(
      screen.getByText(
        "All data is synthetic. The league, clubs, players and partners are fictional.",
      ),
    ).toBeInTheDocument();
  });
});
