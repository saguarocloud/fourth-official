import { CorrectionBoard } from "@/components/match-live/CorrectionBoard";
import type { Incident as IncidentView } from "@/domain/corrections";

// The studio's clock, as the top bar shows it.
const STUDIO_TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function deskTime(ms: number): string {
  return `${(ms / 1000).toFixed(ms < 1000 ? 3 : 1)} s`;
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

const KINDS = { EVENT_VOIDED: "Event voided", EVENT_AMENDED: "Event amended" } as const;

/** The correction itself: what changed on the board, when, and what the desk made of it. */
export function Incident({ incident }: { incident: IncidentView }) {
  const { correction } = incident;
  const issued = STUDIO_TIME.format(new Date(correction.correction.issuedAt));
  return (
    <section className="incident" aria-labelledby="incident-heading">
      <h2 id="incident-heading" className="incident__title">
        {correction.summary}
      </h2>
      <div className="incident__body">
        <CorrectionBoard
          correction={correction}
          itemsCorrected={incident.changes.filter((c) => c.action.was === "on_air").length}
        />
        <dl className="incident__facts">
          <div>
            <dt>Correction</dt>
            <dd>{KINDS[correction.correction.kind]}</dd>
          </div>
          <div>
            <dt>Corrected event</dt>
            <dd className="tabular">{correction.correction.targetEventId}</dd>
          </div>
          <div>
            <dt>Issued (studio time)</dt>
            <dd className="tabular">{issued}</dd>
          </div>
          <div>
            <dt>Desk time</dt>
            <dd className="tabular">
              {incident.reports.length ? deskTime(incident.elapsedMs) : "Not yet reported"}
            </dd>
          </div>
        </dl>
      </div>
      <p className="incident__summary tabular" role="region" aria-label="Impact">
        {`${plural(incident.items, "item", "items")} · ${plural(incident.partners, "partner", "partners")} · ${plural(incident.languages, "language", "languages")} · ${deskTime(incident.elapsedMs)}`}
      </p>
    </section>
  );
}
