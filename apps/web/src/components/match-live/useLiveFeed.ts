"use client";

import {
  type Connection,
  type Folding,
  RETRY_MS,
  streamReducer,
  useFeedStream,
} from "@/components/matchday/useFeedStream";
import { applyEntry, emptyLive, type LiveMatch } from "@/domain/live";

export type { Connection };
export { RETRY_MS };

const LIVE: Folding<LiveMatch> = { empty: emptyLive, apply: applyEntry };

/** Match Live's reducer: the generic stream reducer over the Match Live view model. */
export const reduceFeed = streamReducer(LIVE);

/** A match's live feed, folded into the Match Live view. */
export function useLiveFeed(
  matchId: string,
  /** Changes when a new run starts, so a stream that ended at full time opens again. */
  runKey: number,
): { live: LiveMatch; connection: Connection } {
  const { view, connection } = useFeedStream(matchId, runKey, LIVE);
  return { live: view, connection };
}
