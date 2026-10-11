"use client";

import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { MatchSwitcher } from "@/components/match-live/MatchSwitcher";
import type { Folding } from "@/components/matchday/useFeedStream";
import { useFeedStream } from "@/components/matchday/useFeedStream";
import { useMatches, useRunKey } from "@/components/matchday/useMatchday";
import { AppShell } from "@/components/shell/AppShell";
import { applyBroadcast, type BroadcastState, emptyBroadcast } from "@/domain/broadcast";
import { incidents } from "@/domain/corrections";
import { isMatchId } from "@/lib/matchId";

import { ChangeBoard } from "./ChangeBoard";
import { ImpactStrip } from "./ImpactStrip";
import { Incident } from "./Incident";
import { correctionsVerdict } from "./verdict";

const FEATURED = "m42";
const BROADCAST: Folding<BroadcastState> = { empty: emptyBroadcast, apply: applyBroadcast };
const KIND_WORDS = { EVENT_VOIDED: "Ruled out", EVENT_AMENDED: "Amended" } as const;

/** The Corrections Center: every correction this match, and every published item it reached. */
export function CorrectionsCenter() {
  const params = useSearchParams();
  const { matches, failed } = useMatches({ availability: false });
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED);
  const matchId = current?.matchId ?? asked;
  const runKey = useRunKey(matchId, current?.state ?? null);
  const { view } = useFeedStream(matchId, runKey, BROADCAST);

  const all = useMemo(() => incidents(view), [view]);
  const [chosen, setChosen] = useState<string | null>(null);
  const [replay, setReplay] = useState(0);
  const incident =
    all.find((i) => i.correction.correction.correctionId === chosen) ?? all.at(-1) ?? null;
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
        {all.length > 0 && (
          <div role="group" aria-label="Corrections this match" className="corrections__keys">
            {all.map((i) => {
              const id = i.correction.correction.correctionId;
              return (
                <button
                  key={id}
                  type="button"
                  className="key"
                  aria-pressed={i === incident}
                  onClick={() => setChosen(id)}
                >
                  <span>{`${KIND_WORDS[i.correction.correction.kind]}: ${i.correction.outText} → ${i.correction.inText}`}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      {incident && (
        <>
          <Incident incident={incident} />
          <section className="corrections__impact" aria-labelledby="impact-heading">
            <div className="corrections__impact-head">
              <h2 id="impact-heading" className="panel-heading">
                What it reached
              </h2>
              <button
                type="button"
                className="key"
                data-size="sm"
                onClick={() => setReplay((n) => n + 1)}
              >
                <span>Replay</span>
              </button>
            </div>
            <ImpactStrip incident={incident} replay={replay} />
            {incident.changes.length === 0 ? (
              <p className="corrections__none">
                No published item rested on it, or the desk has not reported yet.
              </p>
            ) : (
              <ul className="changes" aria-label="Items corrected" key={replay}>
                {incident.changes.map((change) => (
                  <ChangeBoard key={change.action.itemId} change={change} />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
      <p className="page-footnote">
        All data is synthetic. Corrections arrive from the match data; the corrections desk finds
        every partner item resting on the corrected event and acts as each partner&apos;s policy
        says.
      </p>
    </AppShell>
  );
}
