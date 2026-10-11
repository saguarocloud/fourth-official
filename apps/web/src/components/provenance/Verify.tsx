"use client";

import { BrandMark } from "@/components/shell/BrandMark";

import { ProvenanceRecord } from "./ProvenanceRecord";
import { type Lookup, useProvenance } from "./useProvenance";

const NOTES: Partial<Record<Lookup["status"], string>> = {
  idle: "Checking the record.",
  loading: "Checking the record.",
  missing: "The studio has no record of this graphic.",
  busy: "Too many checks from here. Wait a moment and try again.",
  unavailable: "The check cannot be made just now: the studio's service did not answer.",
};

/** The public Verify page: anyone holding a graphic's item id can see whether the studio
 * published it, as it says, and what became of it. Paper, not the control room. */
export function Verify({ itemId }: { readonly itemId: string }) {
  const { lookup, retry } = useProvenance(itemId);
  return (
    <div data-theme="paper" className="paper">
      <header className="paper__masthead">
        <BrandMark />
        <p className="paper__studio">
          Meridian League Studios <span className="paper__product">· Fourth Official</span>
        </p>
      </header>
      <main id="main" className="paper__main">
        <h1 className="paper__title">Is this graphic what the studio published?</h1>
        {lookup.status === "ready" ? (
          <ProvenanceRecord answer={lookup.answer} />
        ) : (
          <div className="provenance__note" data-status={lookup.status}>
            <p>{NOTES[lookup.status]}</p>
            {(lookup.status === "busy" || lookup.status === "unavailable") && (
              <button type="button" className="key" data-size="sm" onClick={retry}>
                <span>Try again</span>
              </button>
            )}
          </div>
        )}
        <section aria-labelledby="how-heading" className="paper__how">
          <h2 id="how-heading">How this check works</h2>
          <p>
            When a graphic is published, the studio writes down what it said, who wrote it, which
            match events it rests on and how it was checked, and signs that record with the
            studio&apos;s key; the seal names the key. This page asks the studio&apos;s service to
            check the signature against the record as it is stored now: change one word and the
            signature no longer matches.
          </p>
        </section>
      </main>
      <footer className="paper__footer">
        A demonstration. The league, clubs, players and partners are fictional and all match data is
        synthetic.
      </footer>
    </div>
  );
}
