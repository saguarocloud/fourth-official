/*
 * THESIS: the match as a verified wire. Every moment arrives explained, checked and labelled, and
 * a correction visibly amends what was already shown; refuses the stats dashboard of charts.
 * OWN-WORLD: the fourth official's board. Anodised panels, LED scoreline and clock, signal light
 * only for state, OUT/IN boards for corrections.
 * STORY: a producer sees the score, reads each moment as it is verified, opens how it was
 * verified, and watches VAR and the panel correct items already published.
 * FIRST VIEWPORT: title and verdict; match keys and Start matchday; the LED scoreboard; the wire
 * beneath. Corrections in the right rail.
 * FORM: live-text wire, candidate 6 of 7; seed 3417beca.
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
 * verdict, and DESIGN.md.
 */
import { Suspense } from "react";

import { MatchLive } from "@/components/match-live/MatchLive";
import { AppShell } from "@/components/shell/AppShell";

export default function MatchLivePage() {
  return (
    <Suspense
      fallback={
        <AppShell current="/match" studio="Meridian League Studios" replay>
          <header className="page-header">
            <h1>Match Live</h1>
          </header>
        </AppShell>
      }
    >
      <MatchLive />
    </Suspense>
  );
}
