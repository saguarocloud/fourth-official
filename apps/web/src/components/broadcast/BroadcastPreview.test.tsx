import { act, fireEvent, render, screen } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/preview",
  useSearchParams: () => search.value,
}));

import { FakeEventSource, MATCHES } from "@/components/match-live/testing";

import { BroadcastPreview } from "./BroadcastPreview";
import { clockAt, FEED, itemOf } from "./testing";

function serve(matches: unknown) {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(() =>
        matches instanceof Error
          ? Promise.reject(matches)
          : Promise.resolve(new Response(JSON.stringify({ matches }), { status: 200 })),
      ),
  );
}

function stream(): FakeEventSource {
  const latest = FakeEventSource.instances.at(-1);
  if (latest === undefined) throw new Error("no stream");
  return latest;
}

async function played() {
  serve(MATCHES);
  const view = render(<BroadcastPreview />);
  await screen.findByText("Harbour City v Northgate FC · Meridian League");
  act(() => {
    stream().open();
    for (const entry of FEED) stream().emit(entry.kind, entry);
  });
  return view;
}

const monitor = () => document.querySelector(".monitor__stage")!;

describe("BroadcastPreview", () => {
  beforeEach(() => {
    search.value = new URLSearchParams();
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("reads the match's one feed and says how many graphics air and wait", async () => {
    await played();

    expect(stream().url).toBe("/api/matches/m42/stream");
    expect(screen.getByRole("status", { name: "Broadcast verdict" })).toHaveTextContent(
      "7 moments in three voices: 12 graphics cleared for air, 5 pending approval at Tribuna Austral; 4 pulled by corrections.",
    );
    expect(screen.getByRole("heading", { name: "Program: Northlight Sport" })).toBeInTheDocument();
  });

  it("airs the partner's graphic when the match clock reaches it", async () => {
    await played();
    // The third goal graphic: the first two share the air with a correction strap.
    const goal = itemOf("northlight-sport", "lower_third", 2);
    act(() => stream().emit("clock", clockAt(goal)));

    expect(monitor()).toHaveTextContent("Harbour City score");
    expect(monitor()).toHaveTextContent("AI-generated");
    expect(screen.getByRole("button", { name: /Northlight Sport.*on air/ })).toBeInTheDocument();
  });

  it("switches partner with keys 1, 2 and 3, and never airs a held graphic", async () => {
    await played();
    act(() => stream().emit("clock", clockAt(itemOf("northlight-sport", "lower_third", 2))));

    fireEvent.keyDown(window, { key: "3" });
    expect(monitor()).toHaveAttribute("data-tenant", "rheinblick-sport");
    expect(monitor()).toHaveTextContent("KI-generiert");
    fireEvent.keyDown(window, { key: "2" });
    expect(monitor()).toHaveAttribute("data-tenant", "tribuna-austral");
    expect(monitor()).not.toHaveTextContent("Generado con IA");
    expect(document.querySelector(".gfx-third")).toBeNull();
    expect(monitor()).toHaveTextContent("1:0".replace(":", "–"));
  });

  it("previews a rundown row and returns to program on Escape", async () => {
    await played();
    fireEvent.keyDown(window, { key: "2" });
    const goal = screen.getAllByRole("button", { name: /^Goal, / }).at(-1)!;

    fireEvent.click(goal);
    expect(screen.getByRole("heading", { name: "Preview: Tribuna Austral" })).toBeInTheDocument();
    expect(screen.getByText("Pending approval · held off air")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("heading", { name: "Program: Tribuna Austral" })).toBeInTheDocument();
  });

  it("returns to program from the key, and toggles the safe areas with G", async () => {
    await played();
    fireEvent.click(screen.getAllByRole("button", { name: /^Goal/ })[0]!);

    fireEvent.click(screen.getByRole("button", { name: "Back to program" }));
    expect(screen.getByRole("heading", { name: /^Program/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Safe areas" })).toHaveTextContent("G");
    fireEvent.keyDown(window, { key: "g" });
    expect(screen.getByRole("button", { name: "Safe areas" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    fireEvent.click(screen.getByRole("button", { name: "Safe areas" }));
    expect(document.querySelector(".monitor__guides")).toBeNull();
  });

  it("ignores keys typed into a field and keys held with a modifier", async () => {
    await played();
    const field = document.createElement("input");
    document.body.append(field);

    fireEvent.keyDown(field, { key: "3" });
    fireEvent.keyDown(window, { key: "2", metaKey: true });
    expect(monitor()).toHaveAttribute("data-tenant", "northlight-sport");
    field.remove();
  });

  it("opens the match asked for in the address", async () => {
    search.value = new URLSearchParams("match=m43");
    serve(MATCHES);
    render(<BroadcastPreview />);

    await screen.findByText("Kingsbridge Athletic v Ashford Vale · Meridian League");
    expect(stream().url).toBe("/api/matches/m43/stream");
    expect(screen.getByText(/Nothing on the wire yet/)).toBeInTheDocument();
    expect(screen.getByText(/No graphics yet/)).toBeInTheDocument();
  });

  it("says the match is under way before the first moment", async () => {
    serve(MATCHES.map((m) => ({ ...m, state: "running" })));
    render(<BroadcastPreview />);

    expect(await screen.findByText(/The match is under way/)).toBeInTheDocument();
  });

  it("says when the match service is down, and when the stream reconnects", async () => {
    serve(new Error("offline"));
    render(<BroadcastPreview />);

    expect(await screen.findByText(/The match service is unavailable/)).toBeInTheDocument();
    act(() => stream().fail());
    expect(screen.getByText(/Reconnecting; nothing will be missed/)).toBeInTheDocument();
  });

  it("says it is loading until the matches are known, and never asks for the start key", async () => {
    serve(MATCHES);
    render(<BroadcastPreview />);

    expect(screen.getByRole("status", { name: "Broadcast verdict" })).toHaveTextContent(
      "Loading the matchday.",
    );
    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    const asked = vi.mocked(fetch).mock.calls.map(([url]) => String(url));
    expect(asked).not.toContain("/api/matchday");
  });

  it("forgets the row chosen when the match changes", async () => {
    const view = await played();
    fireEvent.click(screen.getAllByRole("button", { name: /^Goal/ })[0]!);
    expect(screen.getByRole("heading", { name: /^Preview/ })).toBeInTheDocument();

    search.value = new URLSearchParams("match=m43");
    view.rerender(<BroadcastPreview />);
    await screen.findByText("Kingsbridge Athletic v Ashford Vale · Meridian League");
    search.value = new URLSearchParams("match=m42");
    view.rerender(<BroadcastPreview />);
    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    act(() => {
      for (const entry of FEED) stream().emit(entry.kind, entry);
    });

    expect(screen.getByRole("heading", { name: /^Program/ })).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = await played();
    fireEvent.click(screen.getAllByRole("button", { name: /^Goal/ })[0]!);

    // jsdom cannot compute colour contrast; contrast is checked against the token values instead.
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
