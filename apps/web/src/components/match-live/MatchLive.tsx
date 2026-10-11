"use client";

import { ArrowDown } from "lucide-react";
import { useSearchParams } from "next/navigation";

import { AppShell } from "@/components/shell/AppShell";
import type { CorrectionEntry } from "@/contracts/feed";
import { FEATURED_MATCH, isMatchId } from "@/lib/matchId";
import { liveVerdict, type LiveItem, type RunState } from "@/domain/live";

import { CorrectionBoard } from "./CorrectionBoard";
import { LiveScoreboard } from "./LiveScoreboard";
import { LiveWire } from "./LiveWire";
import { MatchSwitcher } from "./MatchSwitcher";
import { StartMatchday } from "./StartMatchday";
import { useLiveFeed } from "./useLiveFeed";
import { useMatches, useRunKey } from "@/components/matchday/useMatchday";

function linkTo(item: LiveItem | undefined): string | undefined {
  return item ? `#moment-${item.moment.momentId}` : undefined;
}

export function MatchLive() {
  const params = useSearchParams();
  const { matches, availability, failed, refresh } = useMatches();
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED_MATCH;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED_MATCH);
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
