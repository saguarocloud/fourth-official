import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeEventSource, FEED } from "@/components/match-live/testing";
import { applyBroadcast, type BroadcastState, emptyBroadcast } from "@/domain/broadcast";

import { type Folding, useFeedStream } from "./useFeedStream";

const BROADCAST: Folding<BroadcastState> = { empty: emptyBroadcast, apply: applyBroadcast };

describe("useFeedStream", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  const source = () => FakeEventSource.instances.at(-1)!;

  it("knows which run it is reading, from the events' ids and from a reset", () => {
    const { result } = renderHook(() => useFeedStream("m42", 0, BROADCAST));
    expect(result.current.generation).toBeNull();

    act(() => source().emit(FEED[0]!.kind, FEED[0], "4:1"));
    expect(result.current.generation).toBe(4);

    act(() => source().emit("reset", { generation: 5 }));
    expect(result.current.generation).toBe(5);
  });

  it("keeps the run it knows when an id does not say", () => {
    const { result } = renderHook(() => useFeedStream("m42", 0, BROADCAST));

    act(() => source().emit(FEED[0]!.kind, FEED[0], "2:1"));
    act(() => source().emit(FEED[1]!.kind, FEED[1], ""));
    expect(result.current.generation).toBe(2);
  });
});
