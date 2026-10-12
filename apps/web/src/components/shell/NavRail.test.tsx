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

  it("lists screens that are not built yet without linking to them", () => {
    render(<NavRail current="/" />);

    expect(screen.queryByRole("link", { name: /Policy Studio/ })).toBeNull();
    expect(screen.getByText("Policy Studio")).toBeInTheDocument();
  });

  it("is a labelled primary navigation landmark", () => {
    render(<NavRail current="/" />);

    expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
  });
});

describe("NavRail unavailable screens", () => {
  it("tells every user a screen is not available yet", () => {
    render(<NavRail current="/" />);

    expect(screen.getAllByText("(not yet available)").length).toBeGreaterThan(0);
  });
});
