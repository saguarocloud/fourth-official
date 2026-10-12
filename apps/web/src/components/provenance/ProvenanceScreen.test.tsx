import { act, render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/provenance",
  useSearchParams: () => search.value,
}));

import { FEED } from "@/components/broadcast/testing";
import { FakeEventSource, MATCHES } from "@/components/match-live/testing";

import { ProvenanceScreen } from "./ProvenanceScreen";
import { AMENDED_ID, ANSWERS, ON_AIR_ID } from "./testing";

function serve(provenance: (url: string) => Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        url.startsWith("/api/items/") ? provenance(url) : Response.json({ matches: MATCHES }),
      ),
    ),
  );
}

function stream(): FakeEventSource {
  const latest = FakeEventSource.instances.at(-1);
  if (latest === undefined) throw new Error("no stream");
  return latest;
}

const byId = (url: string) =>
  Response.json(ANSWERS[url.split("/")[3]!] ?? ANSWERS[ON_AIR_ID], {
    status: ANSWERS[url.split("/")[3]!] ? 200 : 404,
  });

async function played() {
  const view = render(<ProvenanceScreen />);
  await screen.findByText("Harbour City v Northgate FC · Meridian League");
  act(() => {
    stream().open();
    for (const entry of FEED) stream().emit(entry.kind, entry);
  });
  return view;
}

describe("ProvenanceScreen", () => {
  beforeEach(() => {
    search.value = new URLSearchParams();
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("lists the match's partner items, newest first, each a link to its record", async () => {
    serve(byId);
    await played();

    const items = within(screen.getByRole("navigation", { name: /^Items on record/ })).getAllByRole(
      "link",
    );
    expect(items.length).toBeGreaterThan(10);
    expect(items[0]).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/provenance\?match=m42&item=it-[\w-]+#record$/),
    );
  });

  it("names each item by its headline as rendered, never the template", async () => {
    serve(byId);
    await played();

    const nav = screen.getByRole("navigation", { name: /^Items on record/ });
    expect(nav).not.toHaveTextContent("{{");
    expect(nav).toHaveTextContent("Gol de Harbour City");
  });

  it("heads the list with how many items are on record", async () => {
    serve(byId);
    await played();

    expect(screen.getByRole("heading", { name: /^Items on record · \d+$/ })).toBeInTheDocument();
  });

  it("opens the newest item's record when none is asked for", async () => {
    serve(byId);
    await played();

    const current = within(
      screen.getByRole("navigation", { name: /^Items on record/ }),
    ).getAllByRole("link")[0]!;
    expect(current).toHaveAttribute("aria-current", "page");
  });

  it("opens the item asked for, reads its record, and leads with whether it holds", async () => {
    search.value = new URLSearchParams({ match: "m42", item: AMENDED_ID });
    serve(byId);
    await played();

    expect(await screen.findByText("Signed and unchanged")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Provenance verdict" })).toHaveTextContent(
      "partner items on record for this match. This one is signed and unchanged.",
    );
    expect(screen.getByRole("link", { name: /public verification page/i })).toHaveAttribute(
      "href",
      `/verify/${AMENDED_ID}`,
    );
  });

  it("turns red when the record does not verify", async () => {
    search.value = new URLSearchParams({ match: "m42", item: ON_AIR_ID });
    serve(() =>
      Response.json({
        ...ANSWERS[ON_AIR_ID],
        verification: { valid: false, reason: "the signature does not match" },
      }),
    );
    await played();

    await screen.findByText("Does not verify");
    const verdict = screen.getByRole("status", { name: "Provenance verdict" });
    expect(verdict).toHaveAttribute("data-tone", "red");
    expect(verdict).toHaveTextContent("This record does not verify: the signature does not match.");
  });

  it("says when no record has been issued for the item yet", async () => {
    search.value = new URLSearchParams({ match: "m42", item: ON_AIR_ID });
    serve(() => Response.json({ detail: "No record" }, { status: 404 }));
    await played();

    expect(
      await screen.findByText(/No record has been issued for this item yet/),
    ).toBeInTheDocument();
  });

  it("offers to try again when the record cannot be read", async () => {
    search.value = new URLSearchParams({ match: "m42", item: ON_AIR_ID });
    serve(() => Response.json({}, { status: 503 }));
    await played();

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("asks for the matchday before anything is published", async () => {
    serve(byId);
    render(<ProvenanceScreen />);
    await screen.findByText("Harbour City v Northgate FC · Meridian League");

    expect(screen.getByRole("status", { name: "Provenance verdict" })).toHaveTextContent(
      "No partner item is on record for this match yet.",
    );
  });

  it("has no accessibility violations", async () => {
    search.value = new URLSearchParams({ match: "m42", item: AMENDED_ID });
    serve(byId);
    const { container } = await played();
    await screen.findByText("Signed and unchanged");

    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
