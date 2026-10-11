import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { emptyLive } from "@/domain/live";

import { FakeEventSource, FEED } from "./testing";
import { reduceFeed, RETRY_MS, useLiveFeed } from "./useLiveFeed";

const START = { matchId: "m42", view: emptyLive(0), connection: "connecting" as const };

describe("reduceFeed", () => {
  it("folds entries and resets to a new run's empty picture", () => {
    const withEntry = reduceFeed(START, { type: "entry", entry: FEED[0]! });
    expect(withEntry.view.lastSeq).toBe(FEED[0]!.entrySeq);

    const reset = reduceFeed(withEntry, { type: "reset", generation: 4 });
    expect(reset.view).toEqual(emptyLive(4));
  });

  it("tracks the connection and starts over on subscribe", () => {
    const live = reduceFeed(START, { type: "connection", connection: "live" });
    expect(live.connection).toBe("live");
    expect(reduceFeed(live, { type: "subscribe", matchId: "m43" })).toEqual({
      ...START,
      matchId: "m43",
    });
  });
});

describe("useLiveFeed", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  function source(): FakeEventSource {
    const latest = FakeEventSource.instances.at(-1);
    if (latest === undefined) throw new Error("no EventSource opened");
    return latest;
  }

  it("subscribes to the match's stream and folds what arrives", () => {
    const { result } = renderHook(() => useLiveFeed("m42", 0));
    expect(source().url).toBe("/api/matches/m42/stream");

    act(() => {
      source().open();
      for (const entry of FEED) source().emit(entry.kind, entry);
    });

    expect(result.current.connection).toBe("live");
    expect(result.current.live.items).toHaveLength(7);
    expect(result.current.live.corrections).toHaveLength(2);
  });

  it("ignores entries for another match or that do not parse", () => {
    const { result } = renderHook(() => useLiveFeed("m43", 0));
    act(() => {
      source().emit("clock", FEED[0]);
      source().emit("clock", "not an entry");
    });
    expect(result.current.live.lastSeq).toBe(0);
  });

  it("starts a new picture on reset, whatever the payload", () => {
    const { result } = renderHook(() => useLiveFeed("m42", 0));
    act(() => source().emit(FEED[0]!.kind, FEED[0]));
    act(() => source().emit("reset", { generation: 3 }));
    expect(result.current.live).toEqual(emptyLive(3));

    act(() => source().emit("reset", { generation: "x" }));
    expect(result.current.live.generation).toBe(0);
  });

  it("closes the stream when the run ends, and reopens for a new run", () => {
    const { result, rerender } = renderHook(({ run }) => useLiveFeed("m42", run), {
      initialProps: { run: 0 },
    });
    const first = source();
    act(() => first.emit("end", { generation: 1 }));
    expect(result.current.connection).toBe("ended");
    expect(first.readyState).toBe(FakeEventSource.CLOSED);

    rerender({ run: 1 });
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(result.current.connection).toBe("connecting");
  });

  it("reports reconnecting while the browser retries", () => {
    const { result } = renderHook(() => useLiveFeed("m42", 0));
    act(() => source().fail());
    expect(result.current.connection).toBe("reconnecting");
  });

  it("reopens a stream the browser gave up on, keeping what it has", () => {
    vi.useFakeTimers();
    try {
      const { result } = renderHook(() => useLiveFeed("m42", 0));
      act(() => source().emit(FEED[0]!.kind, FEED[0]));
      const first = source();

      act(() => first.fail(true));
      expect(result.current.connection).toBe("reconnecting");
      act(() => vi.advanceTimersByTime(RETRY_MS));

      expect(FakeEventSource.instances).toHaveLength(2);
      expect(source().url).toBe("/api/matches/m42/stream");
      expect(result.current.live.lastSeq).toBe(FEED[0]!.entrySeq);
    } finally {
      vi.useRealTimers();
    }
  });

  it("never shows one match's feed under another", () => {
    const { result, rerender } = renderHook(({ id }) => useLiveFeed(id, 0), {
      initialProps: { id: "m42" },
    });
    act(() => source().emit(FEED[0]!.kind, FEED[0]));

    rerender({ id: "m43" });

    expect(result.current.live.lastSeq).toBe(0);
  });

  it("closes the stream on unmount", () => {
    const { unmount } = renderHook(() => useLiveFeed("m42", 0));
    unmount();
    expect(source().readyState).toBe(FakeEventSource.CLOSED);
  });
});
