"use client";

import { ArrowDown } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/shell/AppShell";
import type { CorrectionEntry } from "@/contracts/feed";
import { isMatchId } from "@/lib/matchId";
import { liveVerdict, type LiveItem, type RunState } from "@/domain/live";

import { CorrectionBoard } from "./CorrectionBoard";
import { LiveScoreboard } from "./LiveScoreboard";
import { LiveWire } from "./LiveWire";
import { MatchSwitcher } from "./MatchSwitcher";
import { StartMatchday } from "./StartMatchday";
import type { MatchdayAvailability, MatchSummary } from "./types";
import { useLiveFeed } from "./useLiveFeed";

const POLL_MS = 5000;
const FEATURED = "m42";

interface Poll {
  readonly matches: readonly MatchSummary[];
  readonly availability: MatchdayAvailability | null;
}

async function poll(signal: AbortSignal): Promise<Poll> {
  const [listed, available] = await Promise.allSettled([
    fetch("/api/matches", { cache: "no-store", signal }),
    fetch("/api/matchday", { cache: "no-store", signal }),
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
function useMatches(): {
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
        const answer = await poll(controller.signal);
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
  }, [tick]);

  return {
    matches: latest?.matches ?? null,
    availability: latest?.availability ?? null,
    failed,
    refresh,
  };
}

function linkTo(item: LiveItem | undefined): string | undefined {
  return item ? `#moment-${item.moment.momentId}` : undefined;
}

interface Seen {
  readonly matchId: string;
  readonly state: RunState;
}

/** A new run key whenever the match on screen starts running again, so its stream reopens. The
 * first state seen for a match is where it stands, not a change. */
function useRunKey(matchId: string, state: RunState | null): number {
  const [key, setKey] = useState(0);
  const [seen, setSeen] = useState<Seen | null>(null);
  if (state !== null && (seen?.matchId !== matchId || seen.state !== state)) {
    if (seen?.matchId === matchId && state === "running") setKey(key + 1);
    setSeen({ matchId, state });
  }
  return key;
}

export function MatchLive() {
  const params = useSearchParams();
  const { matches, availability, failed, refresh } = useMatches();
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED);
  const matchId = current?.matchId ?? asked;
  const state: RunState = current?.state ?? "idle";
  const runKey = useRunKey(matchId, current?.state ?? null);
  const { live, connection } = useLiveFeed(matchId, runKey);
  const verdict = failed
    ? {
        tone: "red" as const,
        text: "The match service is unavailable. Retrying every few seconds.",
      }
    : liveVerdict(live, state);
  const running = matches?.some((m) => m.state === "running") ?? false;
  const corrections = [...live.corrections].reverse();
  const corrected = (correction: CorrectionEntry) =>
    live.items.filter(
      (item) => item.correction?.correction.correctionId === correction.correction.correctionId,
    );

  const rail = (
    <section aria-labelledby="corrections-heading">
      <h2 id="corrections-heading" className="panel-heading">
        Corrections
      </h2>
      {corrections.length === 0 ? (
        <p className="live-rail__empty">
          When VAR rules a goal out or a scorer is reassigned, the correction appears here with
          every published item it reached.
        </p>
      ) : (
        <ol className="live-rail__corrections">
          {corrections.map((correction) => (
            <li key={correction.correction.correctionId}>
              <CorrectionBoard
                correction={correction}
                itemsCorrected={corrected(correction).length}
                href={linkTo(corrected(correction)[0])}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  );

  return (
    <AppShell current="/match" studio="Meridian League Studios" replay rail={rail}>
      <header className="page-header">
        <h1>Match Live</h1>
        {current && <p>{`${current.homeName} v ${current.awayName} · Meridian League`}</p>}
        <p role="status" aria-label="Match verdict" className="verdict" data-tone={verdict.tone}>
          <span aria-hidden="true" className="verdict__lamp" />
          {verdict.text}
        </p>
        {corrections.length > 0 && (
          <a className="match-live__jump" href="#corrections-heading">
            {`${corrections.length} ${corrections.length === 1 ? "correction" : "corrections"}`}
            <ArrowDown aria-hidden="true" strokeWidth={1.75} />
          </a>
        )}
      </header>
      <div className="match-live__controls">
        {matches && <MatchSwitcher matches={matches} current={matchId} />}
        <StartMatchday running={running} availability={availability} onStarted={refresh} />
      </div>
      {current && <LiveScoreboard names={current} clock={live.clock} state={state} />}
      <LiveWire live={live} connection={connection} state={state} />
      <p className="page-footnote">
        All data is synthetic. The league, clubs, players and partners are fictional. Numbers and
        names in each insight are rendered by code from verified evidence.
      </p>
    </AppShell>
  );
}
