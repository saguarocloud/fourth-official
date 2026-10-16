import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import fixture from "@/fixtures/operations.json";

import { POLL_MS, useOperations } from "./useOperations";

function serve(...answers: (Response | Error)[]) {
  const fetch = vi.fn();
  for (const answer of answers) {
    if (answer instanceof Error) fetch.mockRejectedValueOnce(answer);
    else fetch.mockResolvedValueOnce(answer);
  }
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("useOperations", () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reads the report through the web app's own route", async () => {
    const fetch = serve(Response.json(fixture));
    const { result } = renderHook(() => useOperations());

    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(fetch).toHaveBeenCalledWith(
      "/api/operations",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("reads it again every few seconds while a run plays", async () => {
    const fetch = serve(Response.json(fixture), Response.json(fixture));
    renderHook(() => useOperations());
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });

    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("keeps the last report on show when a read fails, and says it is stale", async () => {
    serve(Response.json(fixture), new TypeError("offline"));
    const { result } = renderHook(() => useOperations());
    await waitFor(() => expect(result.current.status).toBe("ready"));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });

    await waitFor(() => expect(result.current).toMatchObject({ status: "ready", stale: true }));
  });

  it("is unavailable when nothing has been read and the API does not answer", async () => {
    serve(Response.json({ detail: "x" }, { status: 502 }));
    const { result } = renderHook(() => useOperations());

    await waitFor(() => expect(result.current.status).toBe("unavailable"));
  });

  it("refuses an answer that is not a report", async () => {
    serve(Response.json({ matches: "none" }));
    const { result } = renderHook(() => useOperations());

    await waitFor(() => expect(result.current.status).toBe("unavailable"));
  });
});
