import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { layoutText } from "@/lib/led/glyphs";

import { LedReadout } from "./LedReadout";

describe("LedReadout", () => {
  it("exposes its text to assistive technology as one image", () => {
    render(<LedReadout text="67:12" />);

    expect(screen.getByRole("img", { name: "67:12" })).toBeInTheDocument();
  });

  it("uses a spoken label when the visual text is an abbreviation", () => {
    render(<LedReadout text="HCY" label="Harbour City" />);

    expect(screen.getByRole("img", { name: "Harbour City" })).toBeInTheDocument();
  });

  it("draws one dot per matrix cell and lights exactly the glyph's dots", () => {
    const { container } = render(<LedReadout text="2-1" />);
    const expected = layoutText("2-1");

    expect(container.querySelectorAll("circle")).toHaveLength(expected.dots.length);
    expect(container.querySelectorAll('circle[data-lit="true"]')).toHaveLength(
      expected.dots.filter((d) => d.lit).length,
    );
  });

  it("sizes the matrix in whole-dot steps so dots stay crisp", () => {
    const { container } = render(<LedReadout text="1" dotSize={3} />);
    const svg = container.querySelector("svg");

    // 5 columns and 7 rows at a 3px dot plus 1px gap, minus the trailing gap.
    expect(svg).toHaveAttribute("width", String(5 * 4 - 1));
    expect(svg).toHaveAttribute("height", String(7 * 4 - 1));
  });

  it("carries its signal tone for styling", () => {
    const { container } = render(<LedReadout text="0" tone="red" />);

    expect(container.querySelector("svg")).toHaveAttribute("data-tone", "red");
  });
});
