import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NavRail } from "./NavRail";

describe("NavRail", () => {
  it("marks the current screen", () => {
    render(<NavRail current="/" />);

    expect(screen.getByRole("link", { name: "Control Room" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("links every screen, Operations included", () => {
    render(<NavRail current="/operations" />);

    expect(screen.getAllByRole("link")).toHaveLength(9);
    expect(screen.getByRole("link", { name: "Operations" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("is a labelled primary navigation landmark", () => {
    render(<NavRail current="/" />);

    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  });
});
