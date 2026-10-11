"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { MatchSwitcher } from "@/components/match-live/MatchSwitcher";
import type { Folding } from "@/components/matchday/useFeedStream";
import { useFeedStream } from "@/components/matchday/useFeedStream";
import { useMatches, useRunKey } from "@/components/matchday/useMatchday";
import { AppShell } from "@/components/shell/AppShell";
import { applyBroadcast, type BroadcastState, emptyBroadcast } from "@/domain/broadcast";
import { type Incident as IncidentView, incidents, leading } from "@/domain/corrections";
import { FEATURED_MATCH, isMatchId } from "@/lib/matchId";

import { ChangeBoard } from "./ChangeBoard";
import { ImpactStrip } from "./ImpactStrip";
import { Incident } from "./Incident";
import { KIND_NAMES } from "./kinds";
import { correctionsVerdict } from "./verdict";

const BROADCAST: Folding<BroadcastState> = { empty: emptyBroadcast, apply: applyBroadcast };

/** One match's corrections: which one is open, and its replay. Keyed by match, so switching
 * matches starts afresh. */
function MatchCorrections({ all }: { all: readonly IncidentView[] }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const [replay, setReplay] = useState(0);
  const incident = all.find((i) => i.correction.correction.correctionId === chosen) ?? leading(all);

  useEffect(() => {
    // Replayed: the cascade runs again, and focus goes to its first board (the replay is felt
    // even with reduced motion).
    if (replay > 0) document.getElementById("first-change")?.focus({ preventScroll: true });
  }, [replay]);

  if (incident === null) return null;
  const id = incident.correction.correction.correctionId;
  return (
    <>
      <div role="group" aria-labelledby="corrections-keys" className="corrections__keys">
        <span id="corrections-keys" className="panel-heading">
          Corrections this match
        </span>
        {all.map((i) => {
          const key = i.correction.correction.correctionId;
          return (
            <button
              key={key}
              type="button"
              className="key"
              aria-pressed={i === incident}
              onClick={() => {
                setChosen(key);
                setReplay(0);
              }}
            >
              <span>{`${KIND_NAMES[i.correction.correction.kind].key}: ${i.correction.outText} → ${i.correction.inText}`}</span>
            </button>
          );
        })}
      </div>
      <Incident incident={incident} />
      <section className="corrections__impact" aria-labelledby="impact-heading">
        <div className="corrections__impact-head">
          <h2 id="impact-heading" className="panel-heading">
            What it reached
          </h2>
          {incident.changes.length > 0 && (
            <button
              type="button"
              className="key"
              data-size="sm"
              onClick={() => setReplay((n) => n + 1)}
            >
              <span>Replay</span>
            </button>
          )}
        </div>
        <ImpactStrip key={`${id}:${replay}`} incident={incident} replay={replay} />
        {incident.changes.length === 0 ? (
          <p className="corrections__none">
            {incident.reports.length === 0
              ? "The corrections desk has not reported on this correction yet."
              : "No partner item rested on the corrected event."}
          </p>
        ) : (
          <ul className="changes" aria-label="Items corrected" key={`${id}:${replay}`}>
            {incident.changes.map((change, n) => (
              <ChangeBoard key={change.action.itemId} change={change} first={n === 0} />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

/** The Corrections Center: every correction this match, and every published item it reached. */
export function CorrectionsCenter() {
  const params = useSearchParams();
  const { matches, failed } = useMatches({ availability: false });
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED_MATCH;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED_MATCH);
  const matchId = current?.matchId ?? asked;
  const runKey = useRunKey(matchId, current?.state ?? null);
  const { view } = useFeedStream(matchId, runKey, BROADCAST);
  const all = useMemo(() => incidents(view), [view]);
  const verdict = correctionsVerdict(all, failed, matches === null);

  return (
    <AppShell current="/corrections" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Corrections</h1>
        {current && <p>{`${current.homeName} v ${current.awayName} · Meridian League`}</p>}
        <p
          role="status"
          aria-label="Corrections verdict"
          className="verdict"
          data-tone={verdict.tone}
        >
          <span aria-hidden="true" className="verdict__lamp" />
          {verdict.text}
        </p>
      </header>
      <div className="corrections__controls">
        {matches && <MatchSwitcher matches={matches} current={matchId} path="/corrections" />}
      </div>
      <MatchCorrections key={matchId} all={all} />
      <p className="page-footnote">
        All data is synthetic. Corrections arrive from the match data; the corrections desk finds
        every partner item resting on the corrected event and acts as each partner&apos;s policy
        says.
      </p>
    </AppShell>
  );
}
