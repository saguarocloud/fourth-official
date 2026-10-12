import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/proving-ground" }));

import fixture from "@/fixtures/proving-ground.json";

import { ProvingGroundScreen } from "./ProvingGroundScreen";

function serve(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(Response.json(body, { status }))),
  );
}

const withFailure = {
  ...fixture,
  candidate: {
    ...fixture.candidate,
    failures: [
      {
        matchId: "m1003",
        itemId: "it-northlight-sport-in-m1003-goal-HCY-s0287-a1-v1",
        claimId: "cl-1",
        text: "<img src=x onerror=alert(1)> {{player:HCY-19}} scores",
        eventIds: ["m1003-e0287"],
        reasons: ["names HCY-19, who is not credited in its events"],
      },
    ],
  },
};

describe("ProvingGroundScreen", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("leads with the gate's verdict", async () => {
    serve(fixture);
    render(<ProvingGroundScreen />);

    const verdict = await screen.findByRole("status", { name: "Release Gate verdict" });
    expect(verdict).toHaveAttribute("data-tone", "red");
    expect(verdict).toHaveTextContent("blocks Analyst prompt v1.4 against production's v1.2");
    expect(verdict).toHaveTextContent("written by the model, 29.1% against 98.7%");
    expect(screen.getByRole("img", { name: "The call: no-go" })).toBeInTheDocument();
  });

  it("polls every rule, in words as well as lamps", async () => {
    serve(fixture);
    render(<ProvingGroundScreen />);

    const stations = within(await screen.findByRole("list", { name: /^The poll/ })).getAllByRole(
      "listitem",
    );
    expect(stations).toHaveLength(7);
    const written = stations.find((s) => s.textContent?.includes("Written by the model"))!;
    expect(written).toHaveTextContent("No-go");
    expect(written).toHaveTextContent("29.1%");
    expect(written).toHaveTextContent("Production 98.7%");
    expect(written).toHaveTextContent("Rule: may drop 5 points");
    expect(stations[0]).toHaveTextContent("Go");
  });

  it("sets every measure of both runs side by side", async () => {
    serve(fixture);
    render(<ProvingGroundScreen />);

    const table = await screen.findByRole("table", { name: "Every measure, both runs" });
    expect(within(table).getAllByRole("row")).toHaveLength(12);
    expect(table).toHaveTextContent("$0.14");
    expect(screen.getByText(/the gate does not rule on it/)).toBeInTheDocument();
  });

  it("reports the full benchmark run by template", async () => {
    serve(fixture);
    render(<ProvingGroundScreen />);

    const benchmark = await screen.findByRole("region", { name: "The full benchmark" });
    expect(benchmark).toHaveTextContent("100 matches");
    expect(benchmark).toHaveTextContent("0 of 1067");
    expect(benchmark).not.toHaveTextContent(/pass/i);
  });

  it("says when no claim on air was unsupported", async () => {
    serve(fixture);
    render(<ProvingGroundScreen />);

    expect(
      await screen.findByText("No claim on air at full time was unsupported, in either run."),
    ).toBeInTheDocument();
  });

  it("lists an unsupported claim as text, with why it failed", async () => {
    serve(withFailure);
    const { container } = render(<ProvingGroundScreen />);

    const failures = await screen.findByRole("list", { name: "Unsupported claims" });
    expect(failures).toHaveTextContent("names HCY-19, who is not credited in its events");
    expect(failures).toHaveTextContent("<img src=x onerror=alert(1)>");
    expect(container.querySelector("img")).toBeNull();
  });

  it("offers to try again when the results cannot be read", async () => {
    serve({ detail: "x" }, 503);
    render(<ProvingGroundScreen />);

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Release Gate verdict" })).toHaveAttribute(
      "data-tone",
      "red",
    );
  });

  it("has no accessibility violations", async () => {
    serve(withFailure);
    const { container } = render(<ProvingGroundScreen />);
    await screen.findByRole("list", { name: /^The poll/ });

    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
