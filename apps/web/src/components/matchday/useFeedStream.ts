"use client";

import { useEffect, useReducer, useState } from "react";

import type { FeedEntry } from "@/contracts/feed";
import { parseEntry } from "@/domain/live";

export type Connection = "connecting" | "live" | "ended" | "reconnecting";

/** How long to wait before reopening a stream the browser gave up on. */
export const RETRY_MS = 3000;

export interface StreamState<V> {
  /** The match this picture is of. */
  readonly matchId: string;
  readonly view: V;
  readonly connection: Connection;
  /** The run being read (the feed's generation), once an event has said; a decision names it. */
  readonly generation: number | null;
}

export type StreamAction =
  | { readonly type: "subscribe"; readonly matchId: string }
  | { readonly type: "entry"; readonly entry: FeedEntry; readonly generation: number | null }
  | { readonly type: "reset"; readonly generation: number }
  | { readonly type: "connection"; readonly connection: Connection };

/** A feed's view of one match, folded entry by entry: `apply` must ignore replays itself. */
export interface Folding<V> {
  readonly empty: (generation: number) => V;
  readonly apply: (view: V, entry: FeedEntry) => V;
}

export function streamReducer<V>(
  folding: Folding<V>,
): (state: StreamState<V>, action: StreamAction) => StreamState<V> {
  return (state, action) => {
    switch (action.type) {
      case "subscribe":
        return {
          matchId: action.matchId,
          view: folding.empty(0),
          connection: "connecting",
          generation: null,
        };
      case "entry":
        return {
          ...state,
          view: folding.apply(state.view, action.entry),
          generation: action.generation ?? state.generation,
        };
      case "reset":
        return { ...state, view: folding.empty(action.generation), generation: action.generation };
      case "connection":
        return { ...state, connection: action.connection };
    }
  };
}

const KINDS = [
  "clock",
  "moment",
  "insight",
  "correction",
  "tenant_item",
  "correction_report",
] as const;

/** The run an event belongs to, from its id (`generation:entrySeq`); null when it does not say. */
function runOf(lastEventId: string): number | null {
  const [run] = lastEventId.split(":");
  return run && /^[0-9]{1,9}$/.test(run) ? Number(run) : null;
}

function generationOf(data: string): number {
  try {
    const generation = Number((JSON.parse(data) as { generation?: unknown }).generation);
    return Number.isInteger(generation) ? generation : 0;
  } catch {
    return 0;
  }
}

/**
 * A match's feed as server-sent events, folded into a view. The browser's EventSource reconnects
 * on its own with Last-Event-ID; a stream it gives up on is reopened after a pause, keeping the
 * picture (entries already applied are skipped). A `reset` starts a new run's picture, an `end`
 * closes the stream until `runKey` changes.
 */
export function useFeedStream<V>(
  matchId: string,
  /** Changes when a new run starts, so a stream that ended at full time opens again. */
  runKey: number,
  /** Read once, on mount: pass a module constant. */
  folding: Folding<V>,
): StreamState<V> {
  const [reducer] = useState(() => streamReducer(folding));
  const [state, dispatch] = useReducer(reducer, matchId, (id) => ({
    matchId: id,
    view: folding.empty(0),
    connection: "connecting" as Connection,
    generation: null,
  }));
  // Bumped to reopen a stream the browser gave up on.
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    dispatch({ type: "subscribe", matchId });
  }, [matchId, runKey]);

  useEffect(() => {
    const source = new EventSource(`/api/matches/${matchId}/stream`);
    let ended = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const onEntry = (event: MessageEvent<string>) => {
      const entry = parseEntry(event.data, matchId);
      if (entry !== null) dispatch({ type: "entry", entry, generation: runOf(event.lastEventId) });
    };
    for (const kind of KINDS) source.addEventListener(kind, onEntry);
    source.addEventListener("reset", (event: MessageEvent<string>) =>
      dispatch({ type: "reset", generation: generationOf(event.data) }),
    );
    source.addEventListener("end", () => {
      ended = true;
      dispatch({ type: "connection", connection: "ended" });
      source.close();
    });
    source.onopen = () => dispatch({ type: "connection", connection: "live" });
    source.onerror = () => {
      if (ended) return;
      dispatch({ type: "connection", connection: "reconnecting" });
      // A failed reconnect (the API restarting, say) closes the source for good: open a new one.
      if (source.readyState === EventSource.CLOSED) {
        timer = setTimeout(() => setRetry((n) => n + 1), RETRY_MS);
      }
    };
    return () => {
      clearTimeout(timer);
      source.close();
    };
  }, [matchId, runKey, retry]);

  // Until the subscription catches up, a new match shows nothing rather than the last one's feed.
  return state.matchId === matchId
    ? state
    : { matchId, view: folding.empty(0), connection: "connecting", generation: null };
}
