import { render, screen } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ANSWERS, HELD_ID, ON_AIR_ID } from "./testing";
import { Verify } from "./Verify";

function serve(response: Response) {
  const fetch = vi.fn(() => Promise.resolve(response));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("Verify", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("is a page of its own, on paper, outside the control room", async () => {
    serve(Response.json(ANSWERS[ON_AIR_ID]));
    const { container } = render(<Verify itemId={ON_AIR_ID} />);

    expect(container.querySelector("[data-theme='paper']")).not.toBeNull();
    expect(screen.queryByRole("navigation", { name: /screens/i })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Is this graphic what the studio published?",
    );
    expect(await screen.findByText("Signed and unchanged")).toBeInTheDocument();
  });

  it("asks for the one item it names", async () => {
    const fetch = serve(Response.json(ANSWERS[HELD_ID]));
    render(<Verify itemId={HELD_ID} />);

    await screen.findByText("Gol de Harbour City");
    expect(fetch).toHaveBeenCalledWith(`/api/items/${HELD_ID}/provenance`, expect.anything());
  });

  it("explains how the check works, in plain words", async () => {
    serve(Response.json(ANSWERS[ON_AIR_ID]));
    render(<Verify itemId={ON_AIR_ID} />);

    expect(screen.getByRole("heading", { name: "How this check works" })).toBeInTheDocument();
    expect(
      screen.getByText(/change one word and the signature no longer matches/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/signs that record with the studio's key/)).toBeInTheDocument();
  });

  it("says plainly when there is no such record", async () => {
    serve(Response.json({ detail: "No such item." }, { status: 404 }));
    render(<Verify itemId={ON_AIR_ID} />);

    expect(
      await screen.findByText("The studio has no record of this graphic."),
    ).toBeInTheDocument();
  });

  it("says when the check cannot be made just now, and offers to try again", async () => {
    serve(Response.json({}, { status: 503 }));
    render(<Verify itemId={ON_AIR_ID} />);

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("labels the page as a demonstration on synthetic data", () => {
    serve(Response.json(ANSWERS[ON_AIR_ID]));
    render(<Verify itemId={ON_AIR_ID} />);

    expect(screen.getByText(/synthetic/i)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    serve(Response.json(ANSWERS[HELD_ID]));
    const { container } = render(<Verify itemId={HELD_ID} />);
    await screen.findByText("Signed and unchanged");

    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
