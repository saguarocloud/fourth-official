import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StartMatchday } from "./StartMatchday";
import type { MatchdayAvailability } from "./types";

const READY: MatchdayAvailability = { ready: true, reason: null, readyAt: null };

function respond(status: number, body?: unknown) {
  const fetchMock = vi
    .fn()
    .mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function press(onStarted = vi.fn()) {
  render(<StartMatchday running={false} availability={READY} onStarted={onStarted} />);
  await userEvent.click(screen.getByRole("button", { name: "Start matchday" }));
  return onStarted;
}

describe("StartMatchday", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("starts the matchday through the proxy", async () => {
    const fetchMock = respond(202, { status: "started" });
    const onStarted = await press();

    expect(fetchMock).toHaveBeenCalledWith("/api/matchday", { method: "POST" });
    expect(onStarted).toHaveBeenCalledOnce();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("names its state while starting", async () => {
    let finish: (response: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => (finish = resolve))),
    );
    render(<StartMatchday running={false} availability={READY} onStarted={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Start matchday" }));
    expect(screen.getByRole("button", { name: "Starting…" })).toBeDisabled();
    await act(async () => finish(new Response(null, { status: 202 })));
  });

  it("stays starting after the API accepts, until the run shows as running", async () => {
    respond(202, { status: "started" });
    const onStarted = vi.fn();
    const { rerender } = render(
      <StartMatchday running={false} availability={READY} onStarted={onStarted} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Start matchday" }));

    expect(screen.getByRole("button", { name: "Starting…" })).toBeDisabled();
    rerender(<StartMatchday running availability={READY} onStarted={onStarted} />);
    expect(screen.getByRole("button", { name: "Matchday running" })).toBeDisabled();
    rerender(<StartMatchday running={false} availability={READY} onStarted={onStarted} />);
    expect(screen.getByRole("button", { name: "Start matchday" })).toBeEnabled();
  });

  it("stops starting when the next answer says the run is already over", async () => {
    respond(202, { status: "started" });
    const cooling = { ready: false, blockedBy: "cooldown" as const, reason: "x", readyAt: null };
    const { rerender } = render(
      <StartMatchday running={false} availability={READY} onStarted={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Start matchday" }));

    rerender(<StartMatchday running={false} availability={cooling} onStarted={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Starting…" })).not.toBeInTheDocument();
  });

  it("explains a refusal in amber, as a sentence", async () => {
    respond(409, { detail: "a matchday is already running" });
    const onStarted = await press();

    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("A matchday is already running.");
    expect(note).toHaveAttribute("data-tone", "amber");
    expect(onStarted).not.toHaveBeenCalled();
  });

  it("shows other failures in red, with a fallback message", async () => {
    respond(502);
    await press();

    const note = screen.getByRole("status");
    expect(note).toHaveTextContent("The matchday could not start.");
    expect(note).toHaveAttribute("data-tone", "red");
  });

  it("says the service is unavailable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await press();

    expect(screen.getByRole("status")).toHaveTextContent(/unavailable/);
  });

  it("is disabled while a matchday runs, and drops a note that no longer applies", async () => {
    respond(409, { detail: "a matchday is already running" });
    const { rerender } = render(
      <StartMatchday running={false} availability={READY} onStarted={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Start matchday" }));
    expect(screen.getByRole("status")).toBeInTheDocument();

    rerender(<StartMatchday running availability={READY} onStarted={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Matchday running" })).toBeDisabled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("counts down the cooldown, then opens", () => {
    vi.useFakeTimers({ now: new Date("2026-10-11T12:00:00Z") });
    const cooling = {
      ready: false,
      blockedBy: "cooldown" as const,
      reason: "the matchday can be replayed again in 65 seconds",
      readyAt: "2026-10-11T12:01:05+00:00",
    };
    render(<StartMatchday running={false} availability={cooling} onStarted={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Ready in 1:05" })).toBeDisabled();
    act(() => vi.advanceTimersByTime(6000));
    expect(screen.getByRole("button", { name: "Ready in 0:59" })).toBeDisabled();
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByRole("button", { name: "Start matchday" })).toBeEnabled();
  });

  it("says when the daily allowance is spent", () => {
    vi.useFakeTimers({ now: new Date("2026-10-11T12:00:00Z") });
    const spent = {
      ready: false,
      blockedBy: "daily_limit" as const,
      reason: "the matchday has been replayed as often as allowed today",
      readyAt: "2026-10-12T09:30:00+00:00",
    };
    render(<StartMatchday running={false} availability={spent} onStarted={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Start matchday" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(
      "The matchday has been replayed as often as allowed today. Ready again at 09:30 UTC.",
    );
  });
});
