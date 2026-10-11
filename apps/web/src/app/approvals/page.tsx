/*
 * THESIS: one held item owns the desk, read against English; refuses an inbox table of rows.
 * OWN-WORLD: the fourth official's board: panel blacks, hairlines, square-cut keys with caps,
 * amber for waiting; the item itself on its partner's stage, in that partner's graphics.
 * STORY: an editor sees what waits and since when, reads the item as it will air beside the
 * English, learns why it waits, and approves (A) or rejects with a reason (R); the log keeps who
 * decided what and why.
 * FIRST VIEWPORT: title and verdict; match keys and J/K; the call sheet of waiting tickets at the
 * left; the desk: stage, the English, why it waits, the A and R keys; the decisions log beneath.
 * FORM: comparison desk, candidate 5 of 7; seed 230d1588; one item at a time, the next one key
 * away (vertical-feed grammar).
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
 * verdict, and DESIGN.md.
 */
import { Suspense } from "react";

import { Approvals } from "@/components/approvals/Approvals";
import { AppShell } from "@/components/shell/AppShell";

export default function ApprovalsPage() {
  return (
    <Suspense
      fallback={
        <AppShell current="/approvals" studio="Meridian League Studios" replay>
          <header className="page-header">
            <h1>Approvals</h1>
          </header>
        </AppShell>
      }
    >
      <Approvals />
    </Suspense>
  );
}
