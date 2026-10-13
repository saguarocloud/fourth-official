/*
 * THESIS: a partner's policy as a ledger of versions, each with what it changed and why, the next
 * one written in place; refuses a settings page of toggles that overwrite with no history.
 * OWN-WORLD: the fourth official's board: panel blacks, hairlines, square keys; a version's
 * changes read before and after, the old value struck; no state colour for a policy change.
 * STORY: a compliance lead sees where a partner's policy stands and who changed it last, reads
 * what any version changed, writes the next one from the form or raw YAML with a reason, and can
 * put every partner back to the release.
 * FIRST VIEWPORT: title and verdict; partner keys and Reset; the version ledger at the left; the
 * selected version's changes and the policy in full, with Edit on the current one.
 * FORM: change ledger, candidate 3 of 7; seed 1a2624dd.
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
 * verdict, and DESIGN.md.
 */
import { Suspense } from "react";

import { PolicyStudio } from "@/components/policy/PolicyStudio";
import { AppShell } from "@/components/shell/AppShell";

export default function PolicyPage() {
  return (
    <Suspense
      fallback={
        <AppShell current="/policy" studio="Meridian League Studios" replay>
          <header className="page-header">
            <h1>Policy Studio</h1>
          </header>
        </AppShell>
      }
    >
      <PolicyStudio />
    </Suspense>
  );
}
