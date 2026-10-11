import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TallyLight } from "./TallyLight";

describe("TallyLight", () => {
  it("announces when a partner has a graphic on air", () => {
    render(<TallyLight live partner="Northlight Sport" />);

    expect(screen.getByRole("img", { name: "Northlight Sport: on air" })).toHaveAttribute(
      "data-live",
      "true",
    );
  });

  it("announces when nothing is on air", () => {
    render(<TallyLight live={false} partner="Rheinblick Sport" />);

    expect(screen.getByRole("img", { name: "Rheinblick Sport: off air" })).toHaveAttribute(
      "data-live",
      "false",
    );
  });
});

describe("TallyLight announcements", () => {
  it("is not a live region, so many tallies never flood a screen reader", () => {
    const { container } = render(<TallyLight live partner="Northlight Sport" />);

    expect(container.querySelector("[aria-live], [role=status]")).toBeNull();
  });
});
