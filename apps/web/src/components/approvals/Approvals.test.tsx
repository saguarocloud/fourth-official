import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/approvals",
  useSearchParams: () => search.value,
}));

import { FEED } from "@/components/broadcast/testing";
import { FakeEventSource, MATCHES } from "@/components/match-live/testing";
import type { TenantItemEntry } from "@/contracts/feed";

import { Approvals, SETTLE_MS } from "./Approvals";

const TENANTS = {
  tenants: [
    {
      tenantId: "northlight-sport",
      displayName: "Northlight Sport",
      locale: "en-GB",
      disclosureMode: "label-unless-approved",
      approvalRequired: ["recap"],
      dutyEditor: "R. Hale",
    },
    {
      tenantId: "rheinblick-sport",
      displayName: "Rheinblick Sport",
      locale: "de-DE",
      disclosureMode: "eu-strict",
      approvalRequired: ["recap"],
      dutyEditor: "L. Vogt",
    },
    {
      tenantId: "tribuna-austral",
      displayName: "Tribuna Austral",
      locale: "es-MX",
      disclosureMode: "label-all",
      approvalRequired: ["insight", "recap"],
      dutyEditor: "T. Ibarra",
    },
  ],
};
const RUNNING = MATCHES.map((m) => ({ ...m, state: "running" }));
const HELD = FEED.filter(
  (e): e is TenantItemEntry => e.kind === "tenant_item" && e.state === "pending_approval",
);
const NEXT = Math.max(...FEED.map((e) => e.entrySeq)) + 1;

let decisionAnswer: { status: number; body: unknown } = { status: 200, body: {} };

function serve(matches: unknown = RUNNING) {
  const fetch = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>((url) => {
    if (url === "/api/tenants") return Promise.resolve(Response.json(TENANTS));
    if (url.endsWith("/decision")) {
      return Promise.resolve(Response.json(decisionAnswer.body, { status: decisionAnswer.status }));
    }
    return Promise.resolve(Response.json({ matches }));
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function stream(): FakeEventSource {
  const latest = FakeEventSource.instances.at(-1);
  if (latest === undefined) throw new Error("no stream");
  return latest;
}

async function played(matches: unknown = RUNNING) {
  const fetch = serve(matches);
  const view = render(<Approvals />);
  await screen.findByText("Harbour City v Northgate FC · Meridian League");
  act(() => {
    stream().open();
    for (const entry of FEED) stream().emit(entry.kind, entry);
  });
  await screen.findByRole("button", { name: /Approve as T\. Ibarra/ });
  await settle();
  return { view, fetch };
}

function decided(item: TenantItemEntry, decision: "approved" | "rejected"): TenantItemEntry {
  return {
    ...item,
    entrySeq: NEXT,
    state: decision === "approved" ? "on_air" : "rejected",
    approval: {
      editor: "T. Ibarra",
      decidedAt: "2026-10-11T15:04:00.000Z",
      decision,
      ...(decision === "rejected" ? { reason: "Not our tone" } : {}),
    },
  } as TenantItemEntry;
}

/** Wait out the desk's settle time, as an editor reading the item would. */
async function settle() {
  await act(() => new Promise((resolve) => setTimeout(resolve, SETTLE_MS + 20)));
}

const posts = (fetch: ReturnType<typeof serve>) =>
  fetch.mock.calls.filter(([url]) => String(url).endsWith("/decision"));

describe("Approvals", () => {
  beforeEach(() => {
    search.value = new URLSearchParams();
    decisionAnswer = { status: 200, body: {} };
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("lists what waits for an editor, oldest first, and puts the first on the desk", async () => {
    await played();

    expect(screen.getByRole("status", { name: "Approvals verdict" })).toHaveTextContent(
      `${HELD.length} items wait for an editor`,
    );
    const tickets = within(screen.getByRole("list", { name: "Waiting" })).getAllByRole("button");
    expect(tickets).toHaveLength(HELD.length);
    expect(tickets[0]).toHaveAttribute("aria-current", "true");
    expect(document.querySelector(".monitor__stage")).toHaveAttribute(
      "data-tenant",
      "tribuna-austral",
    );
    expect(screen.getByRole("region", { name: "In English" })).toHaveTextContent(
      "Harbour City score",
    );
    expect(
      screen.getByText(/Tribuna Austral's policy sends every insight to an editor/),
    ).toBeInTheDocument();
    expect(screen.getByText(/duty editor \(demo identity\)/)).toBeInTheDocument();
  });

  it("approves with A, naming the run, and moves on once the feed confirms it", async () => {
    const { fetch } = await played();
    const [first] = HELD;

    fireEvent.keyDown(window, { key: "a" });
    await waitFor(() => expect(posts(fetch)).toHaveLength(1));
    const [url, init] = posts(fetch)[0]!;
    expect(url).toBe(
      `/api/tenants/tribuna-austral/matches/m42/items/${first!.overlay.itemId}/decision`,
    );
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      decision: "approved",
      generation: 1,
    });

    act(() => stream().emit("tenant_item", decided(first!, "approved")));
    expect(
      within(screen.getByRole("list", { name: "Waiting" })).getAllByRole("button"),
    ).toHaveLength(HELD.length - 1);
    const log = screen.getByRole("table", { name: "Decisions" });
    expect(log).toHaveTextContent("T. Ibarra");
    expect(log).toHaveTextContent("Approved");
  });

  it("rejects with R and a reason, sent with Enter; Escape puts the reason away", async () => {
    const { fetch } = await played();

    fireEvent.keyDown(window, { key: "r" });
    const reason = screen.getByRole("textbox", { name: "Reason for rejecting" });
    expect(reason).toHaveFocus();
    fireEvent.keyDown(reason, { key: "Escape" });
    expect(screen.queryByRole("textbox", { name: "Reason for rejecting" })).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: "r" });
    const again = screen.getByRole("textbox", { name: "Reason for rejecting" });
    fireEvent.change(again, { target: { value: "Not our tone" } });
    fireEvent.keyDown(again, { key: "a" }); // typing in the field is not a shortcut
    fireEvent.submit(again.closest("form")!);

    await waitFor(() => expect(posts(fetch)).toHaveLength(1));
    expect(JSON.parse(String((posts(fetch)[0]![1] as RequestInit).body))).toEqual({
      decision: "rejected",
      generation: 1,
      reason: "Not our tone",
    });
  });

  it("consumes the shortcut's keystroke, so R never lands in the reason", async () => {
    await played();

    const typed = fireEvent.keyDown(window, { key: "r" });

    expect(typed).toBe(false); // default prevented
    expect(screen.getByRole("textbox", { name: "Reason for rejecting" })).toHaveValue("");
  });

  it("will not send a rejection without a reason", async () => {
    const { fetch } = await played();
    fireEvent.click(screen.getByRole("button", { name: /^Reject/ }));

    fireEvent.submit(
      screen.getByRole("textbox", { name: "Reason for rejecting" }).closest("form")!,
    );

    expect(screen.getByText("Give a reason of one line, without links.")).toBeInTheDocument();
    expect(posts(fetch)).toHaveLength(0);
  });

  it("says why a decision was refused", async () => {
    decisionAnswer = { status: 409, body: { detail: "this item is not awaiting a decision" } };
    await played();

    fireEvent.click(screen.getByRole("button", { name: /Approve as T\. Ibarra/ }));

    expect(
      await screen.findByText(/^"Gol de Harbour City": This item is not awaiting a decision\.$/),
    ).toBeInTheDocument();
  });

  it("moves through the queue with J and K", async () => {
    await played();
    const tickets = () =>
      within(screen.getByRole("list", { name: "Waiting" })).getAllByRole("button");

    fireEvent.keyDown(window, { key: "j" });
    expect(tickets()[1]).toHaveAttribute("aria-current", "true");
    fireEvent.keyDown(window, { key: "k" });
    expect(tickets()[0]).toHaveAttribute("aria-current", "true");
    fireEvent.click(tickets()[2]!);
    expect(tickets()[2]).toHaveAttribute("aria-current", "true");
  });

  it("offers only Reject for an item a correction has since changed", async () => {
    await played();
    const targets = new Set(
      FEED.flatMap((e) => (e.kind === "correction" ? [e.correction.targetEventId] : [])),
    );
    const index = HELD.findIndex((i) =>
      i.localized?.claims.some((c) => c.evidence.eventIds.some((id) => targets.has(id))),
    );

    fireEvent.click(
      within(screen.getByRole("list", { name: "Waiting" })).getAllByRole("button")[index]!,
    );

    expect(
      screen.getByText(/A correction has since changed this item's facts/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Approve/ })).toBeDisabled();
  });

  it("at full time, says held items stay off air and decides nothing", async () => {
    await played(MATCHES);

    expect(screen.getByRole("status", { name: "Approvals verdict" })).toHaveTextContent(
      `Full time. ${HELD.length} held items stayed off air.`,
    );
    expect(screen.getByRole("button", { name: /Approve as T\. Ibarra/ })).toBeDisabled();
  });

  it("says when nothing waits", async () => {
    search.value = new URLSearchParams("match=m43");
    serve();
    render(<Approvals />);

    await screen.findByText("Kingsbridge Athletic v Ashford Vale · Meridian League");
    expect(screen.getByRole("status", { name: "Approvals verdict" })).toHaveTextContent(
      "Nothing waits for an editor.",
    );
  });

  it("puts focus on the queue when the editor decides the last item", async () => {
    const { fetch } = await played();
    // Others decide everything but the first item, which no correction has touched.
    const others = HELD.slice(1);
    for (const [n, item] of others.entries()) {
      act(() => stream().emit("tenant_item", { ...decided(item, "rejected"), entrySeq: NEXT + n }));
    }
    await settle();

    fireEvent.keyDown(window, { key: "a" });

    await waitFor(() => expect(posts(fetch)).toHaveLength(1));
    await waitFor(() => expect(screen.getByRole("heading", { name: /Waiting/ })).toHaveFocus());
  });

  it("never pulls focus to an item that arrives on its own", async () => {
    serve();
    render(<Approvals />);
    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    const elsewhere = screen.getByRole("link", { name: /HCY v NGT/ });
    elsewhere.focus();

    act(() => {
      for (const entry of FEED) stream().emit(entry.kind, entry);
    });
    await screen.findByRole("button", { name: /Approve as T\. Ibarra/ });

    expect(elsewhere).toHaveFocus();
  });

  it("before the match, the empty call sheet does not speak of full time", async () => {
    serve(MATCHES.map((m) => ({ ...m, state: "idle" })));
    render(<Approvals />);

    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    expect(screen.queryByText(/Full time/)).not.toBeInTheDocument();
  });

  it("ignores a held key: one press, one decision", async () => {
    const { fetch } = await played();

    fireEvent.keyDown(window, { key: "a" });
    fireEvent.keyDown(window, { key: "a", repeat: true });
    fireEvent.keyDown(window, { key: "a", repeat: true });

    await waitFor(() => expect(posts(fetch)).toHaveLength(1));
  });

  it("moves on at once after a decision, but will not decide the next item unread", async () => {
    const { fetch } = await played();
    const tickets = () =>
      within(screen.getByRole("list", { name: "Waiting" })).getAllByRole("button");

    fireEvent.keyDown(window, { key: "a" });
    await waitFor(() => expect(tickets()).toHaveLength(HELD.length - 1));
    fireEvent.keyDown(window, { key: "a" }); // a quick second press lands on an unread item
    await settle();

    expect(posts(fetch)).toHaveLength(1);
    expect(screen.getByRole("button", { name: /Approve as T\. Ibarra/ })).toBeEnabled();
  });

  it("says so when the item on the desk is decided elsewhere, and waits before acting", async () => {
    const { fetch } = await played();
    const [first, second] = HELD;

    act(() => stream().emit("tenant_item", decided(first!, "rejected")));

    expect(screen.getByText(/was decided elsewhere/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "In English" })).toBeInTheDocument();
    expect(document.querySelector(".ticket[aria-current='true']")).toHaveTextContent(
      second!.rendered!.headline,
    );
    fireEvent.keyDown(window, { key: "a" });
    expect(posts(fetch)).toHaveLength(0);
  });

  it("does not approve while a rejection is being written", async () => {
    const { fetch } = await played();
    fireEvent.keyDown(window, { key: "r" });
    screen.getByRole("textbox", { name: "Reason for rejecting" }).blur();

    fireEvent.keyDown(window, { key: "a" });

    expect(posts(fetch)).toHaveLength(0);
  });

  it("keeps the typed reason when a rejection is refused", async () => {
    decisionAnswer = {
      status: 503,
      body: { detail: "no room on air this minute; try again shortly" },
    };
    await played();
    fireEvent.keyDown(window, { key: "r" });
    const reason = screen.getByRole("textbox", { name: "Reason for rejecting" });
    fireEvent.change(reason, { target: { value: "Not our tone" } });

    fireEvent.submit(reason.closest("form")!);

    expect(
      await screen.findByText(/No room on air this minute; try again shortly\.$/),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Reason for rejecting" })).toHaveValue(
      "Not our tone",
    );
  });

  it("decides nothing until the feed has said which run it is", async () => {
    serve();
    render(<Approvals />);
    await screen.findByText("Harbour City v Northgate FC · Meridian League");
    act(() => {
      for (const entry of FEED) stream().emit(entry.kind, entry, "");
    });

    expect(await screen.findByRole("button", { name: /Approve as T\. Ibarra/ })).toBeDisabled();
  });

  it("ignores shifted keys and keys while composing text", async () => {
    const { fetch } = await played();

    fireEvent.keyDown(window, { key: "A", shiftKey: true });
    fireEvent.keyDown(window, { key: "a", isComposing: true });

    expect(posts(fetch)).toHaveLength(0);
  });

  it("has no axe violations", async () => {
    const { view } = await played();
    fireEvent.keyDown(window, { key: "r" });

    // jsdom cannot compute colour contrast; contrast is checked against the token values instead.
    const results = await axe.run(view.container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
