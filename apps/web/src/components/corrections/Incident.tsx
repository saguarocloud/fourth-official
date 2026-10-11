import { CorrectionBoard } from "@/components/match-live/CorrectionBoard";
import type { Incident as IncidentView } from "@/domain/corrections";
import { plural } from "@/lib/plural";

import { deskTime, KIND_NAMES } from "./kinds";

// The studio's clock, as the top bar shows it.
const STUDIO_TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

function issuedAt(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? "—" : STUDIO_TIME.format(at);
}

function summary(incident: IncidentView): string {
  if (incident.reports.length === 0) return "The corrections desk has not reported yet.";
  const held = incident.items - incident.onAir;
  const split = held > 0 ? ` (${incident.onAir} on air, ${held} held)` : "";
  return `${plural(incident.items, "partner item", "partner items")}${split} · ${plural(incident.partners, "partner", "partners")} · ${plural(incident.languages, "language", "languages")} · ${deskTime(incident.elapsedMs)}`;
}

/** The correction itself: what changed on the board, when, and what the desk made of it. */
export function Incident({ incident }: { incident: IncidentView }) {
  const { correction } = incident;
  return (
    <section className="incident" aria-labelledby="incident-heading">
      <h2 id="incident-heading" className="incident__title">
        {correction.summary}
      </h2>
      <div className="incident__body">
        <CorrectionBoard correction={correction} itemsCorrected={incident.onAir} brief />
        <dl className="incident__facts">
          <div>
            <dt>Correction</dt>
            <dd>{KIND_NAMES[correction.correction.kind].fact}</dd>
          </div>
          <div>
            <dt>Corrected event</dt>
            <dd className="tabular">{correction.correction.targetEventId}</dd>
          </div>
          <div>
            <dt>Issued (studio time)</dt>
            <dd className="tabular">{issuedAt(correction.correction.issuedAt)}</dd>
          </div>
          <div>
            <dt>Desk reports</dt>
            <dd className="tabular">{incident.reports.length}</dd>
          </div>
        </dl>
      </div>
      <p className="incident__summary tabular">
        <span className="sr-only">What it reached: </span>
        {summary(incident)}
      </p>
    </section>
  );
}
