import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/policy",
  useSearchParams: () => search.value,
}));

import fixture from "@/fixtures/policy-history-rheinblick.json";

import { PolicyStudio } from "./PolicyStudio";

type Handler = (url: string, init?: RequestInit) => Response;

function serve(post?: Handler) {
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST" && post) return Promise.resolve(post(url, init));
    return Promise.resolve(Response.json(fixture));
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

function sent(fetch: ReturnType<typeof serve>): Record<string, unknown> {
  const call = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  return JSON.parse((call![1] as RequestInit).body as string) as Record<string, unknown>;
}

async function opened() {
  const view = render(<PolicyStudio />);
  await screen.findByRole("list", { name: "Versions" });
  return view;
}

describe("PolicyStudio", () => {
  beforeEach(() => {
    search.value = new URLSearchParams({ partner: "rheinblick-sport" });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("leads with where the partner's policy stands and when changes take effect", async () => {
    serve();
    await opened();

    expect(screen.getByRole("status", { name: "Policy verdict" })).toHaveTextContent(
      "Rheinblick Sport is on version 3: reset by L. Vogt at 09:20 UTC. A change governs the next item.",
    );
  });

  it("lists every version newest first, with who, when and why", async () => {
    serve();
    await opened();

    const versions = within(screen.getByRole("list", { name: "Versions" })).getAllByRole(
      "listitem",
    );
    expect(versions.map((v) => v.querySelector("h3")?.textContent)).toEqual([
      "Version 3",
      "Version 2",
      "Version 1",
    ]);
    expect(versions[1]).toHaveTextContent("Edited by L. Vogt at 09:15 UTC");
    expect(versions[1]).toHaveTextContent("Hold insights for the duty editor");
    expect(versions[1]).toHaveTextContent("3 fields");
  });

  it("shows what a version changed, before and after", async () => {
    serve();
    await opened();

    fireEvent.click(screen.getByRole("button", { name: /Version 2/ }));

    const changes = screen.getByRole("table", { name: "What version 2 changed" });
    expect(changes).toHaveTextContent("Held for the duty editor");
    expect(changes).toHaveTextContent("Recaps, Insights");
    expect(changes).toHaveTextContent("Items a minute");
  });

  it("saves an edit from the form with the version it was made on and a reason", async () => {
    const fetch = serve(() => Response.json({ version: 4, action: "edited" }));
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    fireEvent.change(screen.getByLabelText("Items a minute"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Why"), { target: { value: "Quieter for the derby" } });
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    await waitFor(() =>
      expect(sent(fetch)).toMatchObject({ baseVersion: 3, reason: "Quieter for the derby" }),
    );
    expect((sent(fetch).policy as Record<string, unknown>).maxItemsPerMinute).toBe(2);
    await waitFor(() =>
      expect(fetch.mock.calls.filter(([, init]) => init?.method !== "POST").length).toBe(2),
    );
  });

  it("needs a reason before it saves", async () => {
    const fetch = serve();
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));

    expect(screen.getByRole("button", { name: "Save version 4" })).toBeDisabled();
    expect(fetch.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("saves raw YAML from the raw view", async () => {
    const fetch = serve(() => Response.json({ version: 4, action: "edited" }));
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    fireEvent.click(screen.getByRole("tab", { name: "Raw YAML" }));
    const raw = screen.getByLabelText("The policy as YAML") as HTMLTextAreaElement;
    expect(raw.value).toContain('tenantId: "rheinblick-sport"');
    fireEvent.change(raw, {
      target: { value: raw.value.replace("maxItemsPerMinute: 4", "maxItemsPerMinute: 5") },
    });
    fireEvent.change(screen.getByLabelText("Why"), { target: { value: "From the raw view" } });
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    await waitFor(() => expect(sent(fetch).yaml).toContain("maxItemsPerMinute: 5"));
    expect(sent(fetch).policy).toBeUndefined();
  });

  it("shows the API's reason when it refuses an edit", async () => {
    serve(() =>
      Response.json(
        { detail: "The policy is not a valid policy: maxItemsPerMinute: too many" },
        { status: 422 },
      ),
    );
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    fireEvent.change(screen.getByLabelText("Why"), { target: { value: "Try" } });
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("maxItemsPerMinute: too many");
  });

  it("offers to reload when someone saved a version since", async () => {
    serve(() =>
      Response.json({ detail: "version 4 was written since version 3" }, { status: 409 }),
    );
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    fireEvent.change(screen.getByLabelText("Why"), { target: { value: "Try" } });
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "version 4 was written since version 3",
    );
    expect(screen.getByRole("button", { name: "Reload the latest version" })).toBeInTheDocument();
  });

  it("resets every partner to the release after a confirmation", async () => {
    const fetch = serve(() => Response.json({ changes: [] }));
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Reset to the release" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset every partner" }));

    await waitFor(() => expect(sent(fetch)).toEqual({ reason: "Back to the release" }));
  });

  it("has no accessibility violations, reading or editing", async () => {
    serve();
    const { container } = await opened();
    expect((await axe.run(container)).violations).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    expect((await axe.run(container)).violations).toEqual([]);
  });
});
