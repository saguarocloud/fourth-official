import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/match" }));

import MatchLiveError from "./error";

describe("Match Live error", () => {
  it("says the feed could not be shown and retries", async () => {
    const retry = vi.fn();
    render(<MatchLiveError error={new Error("boom")} retry={retry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("The live feed could not be shown.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
