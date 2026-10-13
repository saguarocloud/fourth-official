import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axe from "axe-core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/policy",
  useSearchParams: () => search.value,
}));

import type { PolicyHistory } from "@/contracts/policyHistory";
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

const posts = (fetch: ReturnType<typeof serve>) =>
  fetch.mock.calls.filter(([, init]) => init?.method === "POST").length;

// The fixture with one more version on top: what the API serves once someone else has saved.
function withVersion4(): PolicyHistory {
  const history = fixture as unknown as PolicyHistory;
  const latest = history.versions.at(-1)!;
  return {
    ...history,
    versions: [...history.versions, { ...latest, version: 4, maxItemsPerMinute: 6 }],
    changes: [
      ...history.changes,
      { ...history.changes.at(-1)!, version: 4, action: "edited", fields: ["maxItemsPerMinute"] },
    ],
  };
}

function editing() {
  fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
}

function because(reason: string) {
  fireEvent.change(screen.getByLabelText(/^Why/), { target: { value: reason } });
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
      "Rheinblick Sport is on version 3, reset by L. Vogt at 09:20 UTC: 3 fields changed. Changes apply from the next item.",
    );
  });

  it("lists every version newest first, with who, when and why", async () => {
    serve();
    await opened();

    const versions = within(screen.getByRole("list", { name: "Versions" })).getAllByRole(
      "listitem",
    );
    expect(versions.map((v) => v.querySelector(".ledger__version")?.textContent)).toEqual([
      "Version 3",
      "Version 2",
      "Version 1",
    ]);
    expect(versions[1]).toHaveTextContent("Edited by L. Vogt at 09:15 UTC");
    expect(versions[1]).toHaveTextContent("Hold insights for the duty editor");
    expect(versions[1]).toHaveTextContent("3 fields changed");
    expect(versions[1]).toHaveTextContent("Edited");
    expect(versions[0]!.querySelector("h3")).toBeNull();
  });

  it("shows what a version changed, before and after", async () => {
    serve();
    await opened();

    fireEvent.click(screen.getByRole("button", { name: /Version 2/ }));

    const changes = screen.getByRole("table", { name: "What version 2 changed" });
    expect(changes).toHaveTextContent("Held for the duty editor");
    expect(changes).toHaveTextContent("Added: Insights");
    expect(changes).toHaveTextContent("Items a minute");
  });

  it("saves an edit from the form with the version it was made on and a reason", async () => {
    const fetch = serve(() => Response.json({ version: 4, action: "edited" }));
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    fireEvent.change(screen.getByLabelText("Items a minute"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/^Why/), { target: { value: "Quieter for the derby" } });
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    await waitFor(() =>
      expect(sent(fetch)).toMatchObject({ baseVersion: 3, reason: "Quieter for the derby" }),
    );
    expect((sent(fetch).policy as Record<string, unknown>).maxItemsPerMinute).toBe(2);
    await waitFor(() =>
      expect(fetch.mock.calls.filter(([, init]) => init?.method !== "POST").length).toBe(2),
    );
  });

  it("asks for a reason instead of saving without one", async () => {
    const fetch = serve();
    await opened();

    editing();
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Say why");
    expect(screen.getByLabelText(/^Why/)).toHaveFocus();
    expect(posts(fetch)).toBe(0);
  });

  it("takes terms typed one comma at a time", async () => {
    const fetch = serve(() => Response.json({ version: 4, action: "edited" }));
    await opened();

    editing();
    const tone = screen.getByLabelText("Tone") as HTMLInputElement;
    fireEvent.change(tone, { target: { value: "formal, " } });
    expect(tone.value).toBe("formal, ");
    fireEvent.change(tone, { target: { value: "formal, calm" } });
    because("Calmer");
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    await waitFor(() =>
      expect((sent(fetch).policy as Record<string, unknown>).tone).toEqual(["formal", "calm"]),
    );
  });

  it("keeps a list in the order the form lists it", async () => {
    const fetch = serve(() => Response.json({ version: 4, action: "edited" }));
    await opened();

    editing();
    fireEvent.click(screen.getByRole("checkbox", { name: "Insights" }));
    because("Hold insights");
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    await waitFor(() =>
      expect((sent(fetch).policy as Record<string, unknown>).approvalRequired).toEqual([
        "insight",
        "recap",
      ]),
    );
  });

  it("edits the latency budget in seconds", async () => {
    const fetch = serve(() => Response.json({ version: 4, action: "edited" }));
    await opened();

    editing();
    const latency = screen.getByLabelText("Latency budget") as HTMLInputElement;
    expect(latency.value).toBe("8");
    fireEvent.change(latency, { target: { value: "10.5" } });
    because("Slower desk");
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    await waitFor(() =>
      expect((sent(fetch).policy as Record<string, unknown>).latencyBudgetMs).toBe(10500),
    );
  });

  it("leaves a cleared number blank and will not save it", async () => {
    const fetch = serve();
    await opened();

    editing();
    const rate = screen.getByLabelText("Items a minute") as HTMLInputElement;
    fireEvent.change(rate, { target: { value: "" } });
    expect(rate.value).toBe("");
    because("Try");
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Items a minute");
    expect(posts(fetch)).toBe(0);
  });

  it("carries form edits into the raw view", async () => {
    serve();
    await opened();

    editing();
    fireEvent.change(screen.getByLabelText("Items a minute"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("tab", { name: "Raw YAML" }));

    expect((screen.getByLabelText("The policy as YAML") as HTMLTextAreaElement).value).toContain(
      "maxItemsPerMinute: 2",
    );
  });

  it("keeps raw edits when the form is opened again, and saves them", async () => {
    const fetch = serve(() => Response.json({ version: 4, action: "edited" }));
    await opened();

    editing();
    fireEvent.click(screen.getByRole("tab", { name: "Raw YAML" }));
    const raw = screen.getByLabelText("The policy as YAML") as HTMLTextAreaElement;
    fireEvent.change(raw, {
      target: { value: raw.value.replace("maxItemsPerMinute: 4", "maxItemsPerMinute: 5") },
    });
    fireEvent.click(screen.getByRole("tab", { name: "Form" }));

    expect(screen.getByText(/The raw YAML has edits/)).toBeInTheDocument();
    because("From the raw view");
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));
    await waitFor(() => expect(sent(fetch).yaml).toContain("maxItemsPerMinute: 5"));
  });

  it("moves between the form and the raw view with the arrow keys", async () => {
    serve();
    await opened();

    editing();
    const form = screen.getByRole("tab", { name: "Form" });
    const rawTab = screen.getByRole("tab", { name: "Raw YAML" });
    expect(rawTab).toHaveAttribute("tabindex", "-1");

    fireEvent.keyDown(form, { key: "ArrowRight" });

    expect(rawTab).toHaveAttribute("aria-selected", "true");
    expect(rawTab).toHaveFocus();
  });

  it("keeps the version a draft was made on when the policy moves on under it", async () => {
    let history: PolicyHistory = fixture as unknown as PolicyHistory;
    const fetch = vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST" && url.endsWith("/reset")) {
        return Promise.resolve(Response.json({ changes: [] }));
      }
      if (init?.method === "POST") {
        return Promise.resolve(
          Response.json({ detail: "version 4 was written since version 3" }, { status: 409 }),
        );
      }
      return Promise.resolve(Response.json(history));
    });
    vi.stubGlobal("fetch", fetch);
    await opened();

    editing();
    history = withVersion4();
    fireEvent.click(screen.getByRole("button", { name: "Reset to the release" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset every partner" }));
    await screen.findByText("Version 4", { selector: ".ledger__version" });
    because("Mine");
    fireEvent.click(screen.getByRole("button", { name: /^Save version/ }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
    const edit = fetch.mock.calls.at(-1)![1] as RequestInit;
    expect(JSON.parse(edit.body as string)).toMatchObject({ baseVersion: 3 });
  });

  it("keeps the desk on screen while it reads the policy again", async () => {
    let answer: (response: Response) => void = () => undefined;
    const fetch = vi.fn((_url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(Response.json({ version: 4 }));
      if (fetch.mock.calls.length === 1) return Promise.resolve(Response.json(fixture));
      return new Promise<Response>((resolve) => {
        answer = resolve;
      });
    });
    vi.stubGlobal("fetch", fetch);
    await opened();

    editing();
    because("Again");
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    expect(screen.getByRole("list", { name: "Versions" })).toBeInTheDocument();
    await act(async () => answer(Response.json(withVersion4())));
    expect(await screen.findByRole("heading", { name: /Version 4/ })).toBeInTheDocument();
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
    fireEvent.change(screen.getByLabelText(/^Why/), { target: { value: "From the raw view" } });
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
    fireEvent.change(screen.getByLabelText(/^Why/), { target: { value: "Try" } });
    fireEvent.click(screen.getByRole("button", { name: "Save version 4" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("maxItemsPerMinute: too many");
  });

  it("offers to reload when someone saved a version since", async () => {
    serve(() =>
      Response.json({ detail: "version 4 was written since version 3" }, { status: 409 }),
    );
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    fireEvent.change(screen.getByLabelText(/^Why/), { target: { value: "Try" } });
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
    const reset = screen.getByRole("button", { name: "Reset every partner" });
    fireEvent.click(reset);
    fireEvent.click(reset);

    await waitFor(() => expect(sent(fetch)).toEqual({ reason: "Back to the release" }));
    expect(posts(fetch)).toBe(1);
  });

  it("keeps the keyboard in the reset confirmation and gives it back", async () => {
    serve();
    await opened();

    fireEvent.click(screen.getByRole("button", { name: "Reset to the release" }));
    const confirm = screen.getByRole("group", { name: "Reset to the release" });
    expect(confirm).toHaveTextContent("All 3 partners");
    expect(screen.getByRole("button", { name: "Keep the policies" })).toHaveFocus();

    fireEvent.keyDown(confirm, { key: "Escape" });

    expect(screen.getByRole("button", { name: "Reset to the release" })).toHaveFocus();
  });

  it("has no accessibility violations, reading or editing", async () => {
    serve();
    const { container } = await opened();
    expect((await axe.run(container)).violations).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "Edit this policy" }));
    expect((await axe.run(container)).violations).toEqual([]);
  });
});
