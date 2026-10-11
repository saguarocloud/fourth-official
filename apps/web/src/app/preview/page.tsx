/*
 * THESIS: one truth, three voices: the rundown drives the monitor; refuses a lone video player.
 * OWN-WORLD: the fourth official's board around the frame (panels, LED clock, tally lamps, keys);
 * inside the 16:9 frame each partner's own graphics: navy and aurora green, sunset orange,
 * stone and copper, in a condensed broadcast face.
 * STORY: a producer picks a partner (1, 2, 3), sees what airs at the match clock, picks any row
 * to preview another partner's words, and sees which items wait for an editor.
 * FIRST VIEWPORT: title and verdict; match and partner keys; the program monitor at full width;
 * the rundown beneath with a column per partner.
 * FORM: rundown-driven monitor, candidate 5 of 6; seed 553b37fb; rows ranked by time, columns
 * that never move (split-flap board grammar).
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
 * verdict, and DESIGN.md.
 */
import { Suspense } from "react";

import { BroadcastPreview } from "@/components/broadcast/BroadcastPreview";
import { AppShell } from "@/components/shell/AppShell";

export default function BroadcastPreviewPage() {
  return (
    <Suspense
      fallback={
        <AppShell current="/preview" studio="Meridian League Studios" replay>
          <header className="page-header">
            <h1>Broadcast Preview</h1>
          </header>
        </AppShell>
      }
    >
      <BroadcastPreview />
    </Suspense>
  );
}
