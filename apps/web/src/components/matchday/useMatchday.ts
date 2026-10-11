"use client";

import { useCallback, useEffect, useState } from "react";

import type { MatchdayAvailability, MatchSummary } from "@/components/match-live/types";
import type { RunState } from "@/domain/live";

const POLL_MS = 5000;

interface Poll {
  readonly matches: readonly MatchSummary[];
  readonly availability: MatchdayAvailability | null;
}

async function poll(signal: AbortSignal, withAvailability: boolean): Promise<Poll> {
  const [listed, available] = await Promise.allSettled([
    fetch("/api/matches", { cache: "no-store", signal }),
    withAvailability
      ? fetch("/api/matchday", { cache: "no-store", signal })
      : Promise.reject(new Error("not asked")),
  ]);
  if (listed.status === "rejected") throw listed.reason;
  if (!listed.value.ok) throw new Error(String(listed.value.status));
  const body = (await listed.value.json()) as { matches: MatchSummary[] };
  const availability =
    available.status === "fulfilled" && available.value.ok
      ? ((await available.value.json()) as MatchdayAvailability)
      : null;
  return { matches: body.matches, availability };
}

/** Polls the matchday's matches and whether a run may start, so states and the start key stay
 * current. Each poll cancels the one before it, so a slow answer never overwrites a newer one. */
export function useMatches({ availability: withAvailability = true } = {}): {
  matches: readonly MatchSummary[] | null;
  availability: MatchdayAvailability | null;
  failed: boolean;
  refresh: () => void;
} {
  const [latest, setLatest] = useState<Poll | null>(null);
  const [failed, setFailed] = useState(false);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    let current = new AbortController();
    async function load() {
      current.abort();
      const controller = new AbortController();
      current = controller;
      try {
        const answer = await poll(controller.signal, withAvailability);
        if (!controller.signal.aborted) {
          setLatest(answer);
          setFailed(false);
        }
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void load();
    const timer = setInterval(() => void load(), POLL_MS);
    return () => {
      current.abort();
      clearInterval(timer);
    };
  }, [tick, withAvailability]);

  return {
    matches: latest?.matches ?? null,
    availability: latest?.availability ?? null,
    failed,
    refresh,
  };
}

interface Seen {
  readonly matchId: string;
  readonly state: RunState;
}

/** A new run key whenever the match on screen starts running again, so its stream reopens. The
 * first state seen for a match is where it stands, not a change. */
export function useRunKey(matchId: string, state: RunState | null): number {
  const [key, setKey] = useState(0);
  const [seen, setSeen] = useState<Seen | null>(null);
  if (state !== null && (seen?.matchId !== matchId || seen.state !== state)) {
    if (seen?.matchId === matchId && state === "running") setKey(key + 1);
    setSeen({ matchId, state });
  }
  return key;
}
