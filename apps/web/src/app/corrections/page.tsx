/*
 * THESIS: a correction is a substitution: every published item it reached shown OUT and IN;
 * refuses a log table of affected ids.
 * OWN-WORLD: the fourth official's board: the LED OUT/IN board for the correction, recessed
 * OUT/IN panels for each partner item (struck red when pulled, violet when amended), panel
 * blacks, hairlines, one fan of the impact.
 * STORY: a producer sees what changed, when, and that every partner item resting on it was
 * found and dealt with by its policy, how fast, and can replay it.
 * FIRST VIEWPORT: title and verdict; match keys and correction keys; the incident (board, facts,
 * summary bar); the impact fan with Replay; the item boards beneath.
 * FORM: substitution boards, candidate 6 of 7; seed d5c24a2d; replay re-runs the cascade from
 * the stored report (specimen-slider grammar).
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
 * verdict, and DESIGN.md.
 */
import { Suspense } from "react";

import { CorrectionsCenter } from "@/components/corrections/CorrectionsCenter";
import { AppShell } from "@/components/shell/AppShell";

export default function CorrectionsPage() {
  return (
    <Suspense
      fallback={
        <AppShell current="/corrections" studio="Meridian League Studios" replay>
          <header className="page-header">
            <h1>Corrections</h1>
          </header>
        </AppShell>
      }
    >
      <CorrectionsCenter />
    </Suspense>
  );
}
