import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ITEM_STATES, StatusLamp } from "./StatusLamp";

describe("StatusLamp", () => {
  it.each([
    ["on_air", "On air"],
    ["published", "Published"],
    ["pending_approval", "Pending approval"],
    ["retracted", "Retracted"],
    ["amended", "Amended"],
    ["dropped", "Dropped"],
  ] as const)("names the %s state in words, never colour alone", (state, label) => {
    render(<StatusLamp state={state} />);

    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("gives every state its own icon", () => {
    const icons = ITEM_STATES.map((state) => {
      const { container, unmount } = render(<StatusLamp state={state} />);
      const markup = container.querySelector("svg")?.innerHTML ?? "";
      unmount();
      return markup;
    });

    expect(new Set(icons).size).toBe(ITEM_STATES.length);
  });

  it("can show the lamp alone while keeping the label for screen readers", () => {
    render(<StatusLamp state="retracted" compact />);

    expect(screen.getByText("Retracted")).toHaveClass("sr-only");
  });
});
