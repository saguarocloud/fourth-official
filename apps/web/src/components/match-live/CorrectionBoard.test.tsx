import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CorrectionBoard } from "./CorrectionBoard";
import { correctionsOf } from "./testing";

describe("CorrectionBoard", () => {
  it("lights what went out and what came in, and says what it reached", () => {
    const correction = correctionsOf("EVENT_VOIDED");
    render(<CorrectionBoard correction={correction} itemsCorrected={1} />);

    expect(screen.getByRole("img", { name: "Out: 2-0" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "In: 1-0" })).toBeInTheDocument();
    expect(screen.getByText(correction.summary)).toBeInTheDocument();
    expect(screen.getByText("1 published item corrected.")).toBeInTheDocument();
    expect(screen.getByText(/^Issued \d\d:\d\d:\d\d UTC$/)).toBeInTheDocument();
  });

  it.each([
    [0, "No published item rested on it."],
    [2, "2 published items corrected."],
  ])("counts %i items reached", (count, text) => {
    render(<CorrectionBoard correction={correctionsOf("EVENT_AMENDED")} itemsCorrected={count} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("links to the item it corrected", () => {
    const correction = correctionsOf("EVENT_VOIDED");
    render(<CorrectionBoard correction={correction} itemsCorrected={1} href="#moment-x" />);

    expect(screen.getByRole("link", { name: correction.summary })).toHaveAttribute(
      "href",
      "#moment-x",
    );
  });
});
