/*
 * THESIS: one item's signed record, read as the item annotated; refuses a key-value dump of JSON.
 * OWN-WORLD: the fourth official's board: panel blacks, hairlines, signal lamps; the seal lit green
 * when the record holds and red when it does not.
 * STORY: a producer picks a partner item and sees, first, whether its record holds; then what it
 * said, what each claim rests on, who wrote and checked it, who decided, and where it ended.
 * FIRST VIEWPORT: title and verdict; match keys; the items on record at the left; the record.
 * FORM: annotated item, candidate 6 of 7; seed 310d9828; shared with the public Verify page.
 * FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
 * verdict, and DESIGN.md.
 */
import { Suspense } from "react";

import { ProvenanceScreen } from "@/components/provenance/ProvenanceScreen";
import { AppShell } from "@/components/shell/AppShell";

export default function ProvenancePage() {
  return (
    <Suspense
      fallback={
        <AppShell current="/provenance" studio="Meridian League Studios" replay>
          <header className="page-header">
            <h1>Provenance</h1>
          </header>
        </AppShell>
      }
    >
      <ProvenanceScreen />
    </Suspense>
  );
}
