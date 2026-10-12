import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import fixture from "@/fixtures/proving-ground.json";

import { useProvingGround } from "./useProvingGround";

function serve(...responses: Response[]) {
  const fetch = vi.fn();
  for (const response of responses) fetch.mockResolvedValueOnce(response);
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("useProvingGround", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads the recorded runs through the web app's own route", async () => {
    const fetch = serve(Response.json(fixture));
    const { result } = renderHook(() => useProvingGround());

    expect(result.current.lookup).toEqual({ status: "loading" });
    await waitFor(() =>
      expect(result.current.lookup).toEqual({ status: "ready", ground: fixture }),
    );
    expect(fetch.mock.calls[0]![0]).toBe("/api/proving-ground");
  });

  it.each([
    [503, "unavailable"],
    [502, "unavailable"],
    [429, "busy"],
  ])("reads a %i as %s", async (code, status) => {
    serve(Response.json({ detail: "x" }, { status: code }));
    const { result } = renderHook(() => useProvingGround());

    await waitFor(() => expect(result.current.lookup).toEqual({ status }));
  });

  it("refuses an answer not shaped as the Proving Ground", async () => {
    serve(Response.json({ baseline: "forged" }));
    const { result } = renderHook(() => useProvingGround());

    await waitFor(() => expect(result.current.lookup).toEqual({ status: "unavailable" }));
  });

  it("asks again when told to", async () => {
    const fetch = serve(Response.json({}, { status: 503 }), Response.json(fixture));
    const { result } = renderHook(() => useProvingGround());
    await waitFor(() => expect(result.current.lookup.status).toBe("unavailable"));

    act(() => result.current.retry());

    await waitFor(() => expect(result.current.lookup.status).toBe("ready"));
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
