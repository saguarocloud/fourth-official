import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { KeyButton } from "./KeyButton";

describe("KeyButton", () => {
  it("runs its action when pressed", async () => {
    const onClick = vi.fn();
    render(<KeyButton onClick={onClick}>Approve</KeyButton>);

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is busy and inert while loading", async () => {
    const onClick = vi.fn();
    render(
      <KeyButton loading onClick={onClick}>
        Approve
      </KeyButton>,
    );

    const button = screen.getByRole("button", { name: "Approve" });
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("defaults to a non-submitting button", () => {
    render(<KeyButton>Reject</KeyButton>);

    expect(screen.getByRole("button", { name: "Reject" })).toHaveAttribute("type", "button");
  });

  it("marks its intent for styling", () => {
    render(<KeyButton intent="danger">Retract</KeyButton>);

    expect(screen.getByRole("button", { name: "Retract" })).toHaveAttribute(
      "data-intent",
      "danger",
    );
  });
});
