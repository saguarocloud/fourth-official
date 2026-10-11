"use client";

import { useEffect, useReducer, useState } from "react";

import type { FeedEntry } from "@/contracts/feed";
import { applyEntry, emptyLive, parseEntry, type LiveMatch } from "@/domain/live";

export type Connection = "connecting" | "live" | "ended" | "reconnecting";

interface FeedState {
  /** The match this picture is of. */
  readonly matchId: string;
  readonly live: LiveMatch;
  readonly connection: Connection;
}

export type FeedAction =
  | { readonly type: "subscribe"; readonly matchId: string }
  | { readonly type: "entry"; readonly entry: FeedEntry }
  | { readonly type: "reset"; readonly generation: number }
  | { readonly type: "connection"; readonly connection: Connection };

/** How long to wait before reopening a stream the browser gave up on. */
export const RETRY_MS = 3000;

function initial(matchId: string): FeedState {
  return { matchId, live: emptyLive(0), connection: "connecting" };
}

export function reduceFeed(state: FeedState, action: FeedAction): FeedState {
  switch (action.type) {
    case "subscribe":
      return initial(action.matchId);
    case "entry":
      return { ...state, live: applyEntry(state.live, action.entry) };
    case "reset":
      return { ...state, live: emptyLive(action.generation) };
    case "connection":
      return { ...state, connection: action.connection };
  }
}

const KINDS = ["clock", "moment", "insight", "correction"] as const;

function generationOf(data: string): number {
  try {
    const generation = Number((JSON.parse(data) as { generation?: unknown }).generation);
    return Number.isInteger(generation) ? generation : 0;
  } catch {
    return 0;
  }
}

/**
 * A match's live feed, folded into the Match Live view. The browser's EventSource reconnects on
 * its own with Last-Event-ID; a `reset` starts a new run's picture, an `end` closes the stream
 * until `runKey` changes.
 */
export function useLiveFeed(
  matchId: string,
  /** Changes when a new run starts, so a stream that ended at full time opens again. */
  runKey: number,
): FeedState {
  const [state, dispatch] = useReducer(reduceFeed, matchId, initial);
  // Bumped to reopen a stream the browser gave up on; the picture so far is kept, and entries
  // already applied are skipped when the new stream replays them.
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
      if (entry !== null) dispatch({ type: "entry", entry });
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
  return state.matchId === matchId ? state : initial(matchId);
}
