import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/preview" }));

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("gives a screen without a live rail the rail's space", () => {
    const { container } = render(
      <AppShell current="/preview" studio="Meridian League Studios" replay>
        <p>Screen</p>
      </AppShell>,
    );

    expect(container.firstElementChild).toHaveAttribute("data-rail", "none");
    expect(screen.queryByRole("complementary", { name: "Live rail" })).not.toBeInTheDocument();
  });

  it("keeps the live rail when the screen has one", () => {
    const { container } = render(
      <AppShell current="/" studio="Meridian League Studios" replay rail={<p>Rail</p>}>
        <p>Screen</p>
      </AppShell>,
    );

    expect(container.firstElementChild).not.toHaveAttribute("data-rail");
    expect(screen.getByRole("complementary", { name: "Live rail" })).toHaveTextContent("Rail");
  });
});
