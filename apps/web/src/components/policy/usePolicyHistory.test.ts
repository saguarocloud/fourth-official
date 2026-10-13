import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import fixture from "@/fixtures/policy-history-rheinblick.json";

import { resetPolicies, saveEdit, usePolicyHistory } from "./usePolicyHistory";

function serve(...responses: (Response | Promise<Response>)[]) {
  const fetch = vi.fn();
  for (const response of responses) fetch.mockReturnValueOnce(Promise.resolve(response));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("usePolicyHistory", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads the partner's history through the web app's own route", async () => {
    const fetch = serve(Response.json(fixture));
    const { result } = renderHook(() => usePolicyHistory("rheinblick-sport"));

    expect(result.current.lookup).toEqual({ status: "loading" });
    await waitFor(() =>
      expect(result.current.lookup).toEqual({ status: "ready", history: fixture }),
    );
    expect(fetch.mock.calls[0]![0]).toBe("/api/policies/rheinblick-sport");
  });

  it("is unavailable when the answer is not a history", async () => {
    serve(Response.json({ versions: "x" }));
    const { result } = renderHook(() => usePolicyHistory("rheinblick-sport"));

    await waitFor(() => expect(result.current.lookup).toEqual({ status: "unavailable" }));
  });

  it("reads again when told to", async () => {
    const fetch = serve(Response.json({}, { status: 502 }), Response.json(fixture));
    const { result } = renderHook(() => usePolicyHistory("rheinblick-sport"));
    await waitFor(() => expect(result.current.lookup.status).toBe("unavailable"));

    act(() => result.current.reload());

    await waitFor(() => expect(result.current.lookup.status).toBe("ready"));
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("keeps the partner's last history on show while it reads it again", async () => {
    serve(Response.json(fixture), new Promise<Response>(() => undefined));
    const { result } = renderHook(() => usePolicyHistory("rheinblick-sport"));
    await waitFor(() => expect(result.current.lookup.status).toBe("ready"));

    act(() => result.current.reload());

    expect(result.current.lookup.status).toBe("ready");
  });

  it("never shows one partner's history for another", async () => {
    serve(Response.json(fixture), new Promise<Response>(() => undefined));
    const { result, rerender } = renderHook(({ id }) => usePolicyHistory(id), {
      initialProps: { id: "rheinblick-sport" },
    });
    await waitFor(() => expect(result.current.lookup.status).toBe("ready"));

    rerender({ id: "northlight-sport" });

    expect(result.current.lookup).toEqual({ status: "loading" });
  });
});

describe("saving", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends an edit as the studio and returns the change", async () => {
    const change = { version: 4 };
    const fetch = serve(Response.json(change));

    const outcome = await saveEdit("rheinblick-sport", { yaml: "x", baseVersion: 3, reason: "r" });

    expect(outcome).toEqual({ ok: true, change });
    const [url, init] = fetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/policies/rheinblick-sport");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      "X-Requested-By": "fourth-official",
    });
  });

  it.each([
    [422, "maxItemsPerMinute: too many", "maxItemsPerMinute: too many"],
    [409, "version 4 was written since version 3", "version 4 was written since version 3"],
  ])("returns the API's reason for a %i", async (code, detail, shown) => {
    serve(Response.json({ detail }, { status: code }));

    const outcome = await saveEdit("rheinblick-sport", { yaml: "x", baseVersion: 3, reason: "r" });

    expect(outcome).toEqual({ ok: false, status: code, detail: shown });
  });

  it("says the service did not answer when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    const outcome = await resetPolicies("End");

    expect(outcome).toEqual({
      ok: false,
      status: 0,
      detail: "The policy service did not answer. Nothing was changed.",
    });
  });
});
