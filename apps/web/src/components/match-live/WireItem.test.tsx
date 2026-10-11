import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { itemAt, modelWritten } from "./testing";
import { WireItem } from "./WireItem";

function renderItem(item: Parameters<typeof WireItem>[0]["item"]) {
  render(
    <ol>
      <WireItem item={item} />
    </ol>,
  );
  return screen.getByRole("listitem", { name: item.insight?.rendered.headline ?? /detected/ });
}

describe("WireItem", () => {
  it("shows the minute, kind, verified insight and its template provenance", () => {
    const row = renderItem(itemAt(78));

    expect(within(row).getByText("78'")).toBeInTheDocument();
    expect(within(row).getByText("Goal")).toBeInTheDocument();
    expect(within(row).getByText(/scores for Northgate FC at 78'/)).toBeInTheDocument();
    expect(within(row).getByText("Published")).toBeInTheDocument();
    expect(within(row).getByText("Deterministic template, no model")).toBeInTheDocument();
    expect(within(row).queryByText(/AI/)).not.toBeInTheDocument();
  });

  it("shows first-half added time as broadcast", () => {
    expect(within(renderItem(itemAt(48))).getByText("45+3'")).toBeInTheDocument();
  });

  it("labels a model-written insight and lists every attempt the Verifier judged", () => {
    const item = itemAt(78);
    const row = renderItem({ ...item, insight: modelWritten(item.insight!) });

    expect(within(row).getByText(/AI/)).toBeInTheDocument();
    expect(within(row).getByText(/Verified on attempt 2 · model fast/)).toBeInTheDocument();
    expect(within(row).getByText("refused: bare number")).toBeInTheDocument();
    expect(within(row).getByText("passed every check")).toBeInTheDocument();
  });

  it("says when the template stood in after model attempts, and shows model errors", () => {
    const item = itemAt(78);
    const insight = item.insight!;
    const fellBack = {
      ...insight,
      attempts: [
        { ...insight.attempts[0]!, number: 1, model: "fast", outcome: "error", error: "timeout" },
        { ...insight.attempts[0]!, number: 2, model: "fast", outcome: "error", error: null },
        { ...insight.attempts[0]!, number: 3 },
      ],
    } as typeof insight;
    const row = renderItem({ ...item, insight: fellBack });

    expect(
      within(row).getByText("Deterministic template after 2 model attempts"),
    ).toBeInTheDocument();
    expect(within(row).getByText("model error (timeout)")).toBeInTheDocument();
    expect(within(row).getByText("model error (unknown)")).toBeInTheDocument();
  });

  it("strikes a retracted item and says why", () => {
    const row = renderItem(itemAt(67));

    expect(row).toHaveAttribute("data-state", "retracted");
    expect(within(row).getAllByText("Retracted")).toHaveLength(1);
    expect(within(row).getByText(/ruled out for offside/)).toBeInTheDocument();
  });

  it("leads an amended item with the correction and marks what it superseded", () => {
    const row = renderItem(itemAt(89));

    expect(row).toHaveAttribute("data-state", "amended");
    const strap = within(row).getByText("Corrected").parentElement!;
    const claims = row.querySelector(".wire-item__claims")!;
    expect(strap.compareDocumentPosition(claims) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(row).getByText("As published")).toBeInTheDocument();
    expect(claims).toHaveAttribute("data-superseded", "true");
    expect(within(row).queryByText("Amended")).not.toBeInTheDocument();
  });

  it("links to its heading so a correction can point at it", () => {
    renderItem(itemAt(89));
    expect(document.getElementById(`moment-${itemAt(89).moment.momentId}`)).toHaveRole("heading");
  });

  it("shows a moment still being explained", () => {
    const item = itemAt(12);
    const row = renderItem({ ...item, insight: null, correction: null });

    expect(within(row).getByRole("heading", { name: "Goal detected" })).toHaveClass(
      "wire-item__headline",
      "wire-item__headline--pending",
    );
    expect(within(row).getByText("Explaining and verifying")).toBeInTheDocument();
  });
});
