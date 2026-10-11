import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ANSWERS, ON_AIR_ID } from "./testing";
import { useProvenance } from "./useProvenance";

function serve(...responses: Response[]) {
  const fetch = vi.fn();
  for (const response of responses) fetch.mockResolvedValueOnce(response);
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("useProvenance", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("asks for nothing until an item is chosen", () => {
    const fetch = serve();
    const { result } = renderHook(() => useProvenance(null));

    expect(result.current.lookup).toEqual({ status: "idle" });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("reads the item's record through the web app's own route", async () => {
    const fetch = serve(Response.json(ANSWERS[ON_AIR_ID]));
    const { result } = renderHook(() => useProvenance(ON_AIR_ID));

    expect(result.current.lookup).toEqual({ status: "loading" });
    await waitFor(() =>
      expect(result.current.lookup).toEqual({ status: "ready", answer: ANSWERS[ON_AIR_ID] }),
    );
    expect(fetch.mock.calls[0]![0]).toBe(`/api/items/${ON_AIR_ID}/provenance`);
  });

  it.each([
    [404, { status: "missing" }],
    [429, { status: "busy" }],
    [503, { status: "unavailable" }],
    [502, { status: "unavailable" }],
  ])("reads a %i as %j", async (code, lookup) => {
    serve(Response.json({ detail: "x" }, { status: code }));
    const { result } = renderHook(() => useProvenance(ON_AIR_ID));

    await waitFor(() => expect(result.current.lookup).toEqual(lookup));
  });

  it("refuses an answer that is not shaped as a record", async () => {
    serve(Response.json({ provenance: "forged", verification: { valid: true, reason: null } }));
    const { result } = renderHook(() => useProvenance(ON_AIR_ID));

    await waitFor(() => expect(result.current.lookup).toEqual({ status: "unavailable" }));
  });

  it("is unavailable when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const { result } = renderHook(() => useProvenance(ON_AIR_ID));

    await waitFor(() => expect(result.current.lookup).toEqual({ status: "unavailable" }));
  });

  it("asks again when told to", async () => {
    const fetch = serve(Response.json({}, { status: 503 }), Response.json(ANSWERS[ON_AIR_ID]));
    const { result } = renderHook(() => useProvenance(ON_AIR_ID));
    await waitFor(() => expect(result.current.lookup.status).toBe("unavailable"));

    act(() => result.current.retry());

    expect(result.current.lookup).toEqual({ status: "loading" });
    await waitFor(() => expect(result.current.lookup.status).toBe("ready"));
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("shows the newly chosen item, never the last one's answer", async () => {
    serve(Response.json(ANSWERS[ON_AIR_ID]), new Promise(() => undefined) as never);
    const { result, rerender } = renderHook(({ id }) => useProvenance(id), {
      initialProps: { id: ON_AIR_ID },
    });
    await waitFor(() => expect(result.current.lookup.status).toBe("ready"));

    rerender({ id: "it-tribuna-austral-x-v1" });

    expect(result.current.lookup).toEqual({ status: "loading" });
  });
});
