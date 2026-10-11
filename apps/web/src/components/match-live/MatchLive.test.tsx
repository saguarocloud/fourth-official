import { act, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/match",
  useSearchParams: () => search.value,
}));

import { MatchLive } from "./MatchLive";
import { FakeEventSource, FEED, MATCHES } from "./testing";

const READY = { ready: true, blockedBy: null, reason: null, readyAt: null };

function serve(matches: unknown, availability: unknown = READY) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (matches instanceof Error) return Promise.reject(matches);
      if (url === "/api/matchday") {
        return availability instanceof Error
          ? Promise.reject(availability)
          : Promise.resolve(new Response(JSON.stringify(availability), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ matches }), { status: 200 }));
    }),
  );
}

function stream(): FakeEventSource {
  const latest = FakeEventSource.instances.at(-1);
  if (latest === undefined) throw new Error("no stream");
  return latest;
}

describe("MatchLive", () => {
  beforeEach(() => {
    search.value = new URLSearchParams();
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the featured match finished, with its wire and corrections", async () => {
    serve(MATCHES);
    render(<MatchLive />);

    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    act(() => {
      stream().open();
      for (const entry of FEED) stream().emit(entry.kind, entry);
    });

    expect(screen.getByRole("status", { name: "Match verdict" })).toHaveTextContent(/Full time/);
    expect(screen.getAllByRole("figure")).toHaveLength(2);
    const ruledOut = screen.getByRole("link", { name: /ruled out for offside/ });
    expect(document.querySelector(ruledOut.getAttribute("href")!)).toHaveRole("heading");
    expect(screen.getByRole("link", { name: "2 corrections" })).toHaveAttribute(
      "href",
      "#corrections-heading",
    );
    expect(screen.getByText("Full time")).toBeInTheDocument();
  });

  it("opens the match asked for in the address", async () => {
    search.value = new URLSearchParams("match=m43");
    serve(MATCHES);
    render(<MatchLive />);

    await screen.findByText("Kingsbridge Athletic v Ashford Vale · Meridian League");
    expect(stream().url).toBe("/api/matches/m43/stream");
    expect(screen.getByText(/When VAR rules a goal out/)).toBeInTheDocument();
  });

  it("falls back to the featured match for an unknown one", async () => {
    search.value = new URLSearchParams("match=m99");
    serve(MATCHES);
    render(<MatchLive />);

    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    await waitFor(() => expect(stream().url).toBe("/api/matches/m42/stream"));
  });

  it("opens one stream when the page loads on a running match", async () => {
    serve(MATCHES.map((m) => ({ ...m, state: "running" })));
    render(<MatchLive />);

    await screen.findByRole("button", { name: "Matchday running" });
    expect(FakeEventSource.instances.filter((s) => s.readyState !== 2)).toHaveLength(1);
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("never builds a stream address from a malformed match in the address", async () => {
    search.value = new URLSearchParams("match=../admin");
    serve(MATCHES);
    render(<MatchLive />);

    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    expect(FakeEventSource.instances.map((s) => s.url)).toEqual(["/api/matches/m42/stream"]);
  });

  it("does not let a slow answer overwrite a newer one", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      let slow: (response: Response) => void = () => undefined;
      const answers = [
        () => new Promise<Response>((resolve) => (slow = resolve)),
        () => Promise.resolve(new Response(JSON.stringify({ matches: MATCHES }))),
      ];
      vi.stubGlobal(
        "fetch",
        vi.fn((url: string, init?: RequestInit) => {
          if (url === "/api/matchday") return Promise.resolve(new Response(JSON.stringify(READY)));
          const answer = answers.shift() ?? answers[0]!;
          const pending = answer ?? (() => Promise.resolve(new Response("{}")));
          return new Promise<Response>((resolve, reject) => {
            init?.signal?.addEventListener("abort", () =>
              reject(new DOMException("aborted", "AbortError")),
            );
            void pending().then(resolve);
          });
        }),
      );
      render(<MatchLive />);
      await act(() => vi.advanceTimersByTimeAsync(5000));
      await screen.findByText("Harbour City v Northgate FC · Meridian League");

      const stale = MATCHES.map((m) => ({ ...m, homeName: "Stale" }));
      await act(async () => slow(new Response(JSON.stringify({ matches: stale }))));

      expect(screen.queryByText(/Stale/)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("says when the match service cannot be reached", async () => {
    serve(new Error("down"));
    render(<MatchLive />);

    await waitFor(() =>
      expect(screen.getByRole("status", { name: "Match verdict" })).toHaveTextContent(
        /unavailable/,
      ),
    );
  });

  it("reopens the stream when a new run starts", async () => {
    serve(MATCHES);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<MatchLive />);
      await screen.findByText("Harbour City v Northgate FC · Meridian League");
      const before = FakeEventSource.instances.length;

      serve(MATCHES.map((m) => ({ ...m, state: "running" })));
      await act(() => vi.advanceTimersByTimeAsync(5000));

      await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(before));
      expect(screen.getByRole("button", { name: "Matchday running" })).toBeDisabled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows the cooldown on the start key", async () => {
    const readyAt = new Date(Date.now() + 90_000).toISOString();
    serve(MATCHES, { ready: false, blockedBy: "cooldown", reason: "cooling", readyAt });
    render(<MatchLive />);

    expect(await screen.findByRole("button", { name: /^Ready in 1:[23]\d$/ })).toBeDisabled();
  });

  it("keeps the start key usable when availability cannot be read", async () => {
    serve(MATCHES, new Error("down"));
    render(<MatchLive />);

    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    expect(screen.getByRole("button", { name: "Start matchday" })).toBeEnabled();
  });

  it("has no axe violations", async () => {
    serve(MATCHES);
    const { container } = render(<MatchLive />);
    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    act(() => {
      for (const entry of FEED) stream().emit(entry.kind, entry);
    });

    // jsdom cannot compute colour contrast; contrast is checked against the token values instead.
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
