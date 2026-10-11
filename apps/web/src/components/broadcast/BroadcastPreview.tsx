"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { MatchSwitcher } from "@/components/match-live/MatchSwitcher";
import type { Folding } from "@/components/matchday/useFeedStream";
import { useFeedStream } from "@/components/matchday/useFeedStream";
import { useMatches, useRunKey } from "@/components/matchday/useMatchday";
import { AppShell } from "@/components/shell/AppShell";
import {
  applyBroadcast,
  type BroadcastState,
  emptyBroadcast,
  instant,
  onAir,
  PARTNERS,
  type PartnerId,
  preview,
  rundown,
} from "@/domain/broadcast";
import type { RunState } from "@/domain/live";
import { isMatchId } from "@/lib/matchId";

import { PartnerKeys } from "./PartnerKeys";
import { ProgramMonitor } from "./ProgramMonitor";
import { Rundown } from "./Rundown";
import { verdictFor } from "./verdict";

const FEATURED = "m42";
const BROADCAST: Folding<BroadcastState> = { empty: emptyBroadcast, apply: applyBroadcast };

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    target.closest("input, textarea, select, [contenteditable]") !== null
  );
}

export function BroadcastPreview() {
  const params = useSearchParams();
  const { matches, failed } = useMatches({ availability: false });
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED);
  const matchId = current?.matchId ?? asked;
  const run: RunState | null = matches === null ? null : (current?.state ?? "idle");
  const runKey = useRunKey(matchId, current?.state ?? null);
  const { view, connection } = useFeedStream(matchId, runKey, BROADCAST);

  const [partner, setPartner] = useState<PartnerId>("northlight-sport");
  const [selected, setSelected] = useState<string | null>(null);
  // The row chosen belongs to its match: switching matches returns to program.
  const [shown, setShown] = useState(matchId);
  if (shown !== matchId) {
    setShown(matchId);
    setSelected(null);
  }
  const [guides, setGuides] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || isTyping(event.target)) return;
      const chosen = PARTNERS.find((p) => p.key === event.key);
      if (chosen) setPartner(chosen.id);
      else if (event.key === "g" || event.key === "G") setGuides((on) => !on);
      else if (event.key === "Escape") setSelected(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const rows = useMemo(() => rundown(view), [view]);
  const chosen = selected !== null && rows.some((r) => r.key === selected) ? selected : null;
  const program = chosen ? preview(view, partner, chosen) : onAir(view, partner);
  const airing = new Set(
    PARTNERS.filter((p) => {
      const now = onAir(view, p.id);
      return now.lowerThird !== null || now.strap !== null;
    }).map((p) => p.id),
  );
  const verdict = verdictFor(view, failed, run);
  const active = PARTNERS.find((p) => p.id === partner) ?? PARTNERS[0]!;

  return (
    <AppShell current="/preview" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Broadcast Preview</h1>
        {current && <p>{`${current.homeName} v ${current.awayName} · Meridian League`}</p>}
        <p
          role="status"
          aria-label="Broadcast verdict"
          className="verdict"
          data-tone={verdict.tone}
        >
          <span aria-hidden="true" className="verdict__lamp" />
          {verdict.text}
        </p>
      </header>
      <div className="preview__controls">
        {matches && <MatchSwitcher matches={matches} current={matchId} path="/preview" />}
        <PartnerKeys current={partner} onAir={airing} onChoose={setPartner} />
      </div>
      {connection === "reconnecting" && (
        <p className="preview__notice" role="status">
          Connection lost. Reconnecting; nothing will be missed.
        </p>
      )}
      <div className="preview__desk">
        <div className="preview__monitor">
          <ProgramMonitor
            partner={active}
            program={program}
            mode={chosen ? "preview" : "program"}
            clock={view.clock}
            guides={guides}
          />
          <div className="preview__monitor-keys">
            <button
              type="button"
              className="key"
              data-size="sm"
              aria-pressed={guides}
              aria-keyshortcuts="G"
              onClick={() => setGuides((on) => !on)}
            >
              <span>
                <span className="key-cap" aria-hidden="true">
                  G
                </span>
                Safe areas
              </span>
            </button>
            {chosen && (
              <button
                type="button"
                className="key"
                data-size="sm"
                aria-keyshortcuts="Escape"
                onClick={() => setSelected(null)}
              >
                <span>
                  <span className="key-cap" aria-hidden="true">
                    Esc
                  </span>
                  Back to program
                </span>
              </button>
            )}
          </div>
        </div>
        <Rundown
          rows={rows}
          partner={partner}
          selected={chosen}
          onSelect={setSelected}
          onPartner={setPartner}
          now={view.clock ? instant(view.clock.clock) : null}
        />
      </div>
      <p className="page-footnote">
        All data is synthetic. The partners, league, clubs and players are fictional. Graphics are
        drawn from each partner&apos;s overlay specs over a placeholder pitch; there is no video
        feed.
      </p>
    </AppShell>
  );
}
