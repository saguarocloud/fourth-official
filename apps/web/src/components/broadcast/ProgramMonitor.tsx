import { LedReadout } from "@/components/led/LedReadout";
import type { ClockEntry } from "@/contracts/feed";
import type { Partner, Program } from "@/domain/broadcast";
import { formatMatchClock } from "@/lib/format";

import { CorrectionStrap, LowerThird, ScoreBug } from "./Graphics";

interface ProgramMonitorProps {
  readonly partner: Partner;
  readonly program: Program;
  /** Program follows the match clock; preview shows the rundown row chosen. */
  readonly mode: "program" | "preview";
  readonly clock: ClockEntry | null;
  readonly guides: boolean;
  /** What the stage shows, for screen readers; by default, that the rundown lists it. */
  readonly stageLabel?: string;
}

/** A pitch drawn in the faintest line: the feed the graphics sit over, never real footage. */
function Pitch() {
  return (
    <svg className="monitor__pitch" viewBox="0 0 1920 1080" aria-hidden="true">
      <rect x="160" y="140" width="1600" height="800" />
      <line x1="960" y1="140" x2="960" y2="940" />
      <circle cx="960" cy="540" r="130" />
      <rect x="160" y="340" width="220" height="400" />
      <rect x="1540" y="340" width="220" height="400" />
      <rect x="160" y="450" width="80" height="180" />
      <rect x="1680" y="450" width="80" height="180" />
    </svg>
  );
}

/** One partner's broadcast, as its viewers would see it: the graphics in its own look. */
export function ProgramMonitor({
  partner,
  program,
  mode,
  clock,
  guides,
  stageLabel,
}: ProgramMonitorProps) {
  const lit = mode === "program" && (program.lowerThird !== null || program.strap !== null);
  const time = clock ? formatMatchClock(clock.clock.minute, clock.clock.second) : "00:00";
  return (
    <section className="monitor" aria-labelledby="monitor-heading">
      <header className="monitor__bar">
        <h2 id="monitor-heading" className="monitor__mode">
          <span aria-hidden="true" className="monitor__tally" data-lit={lit || undefined} />
          {mode === "program" ? "Program" : "Preview"}
          <span className="sr-only">{`: ${partner.name}`}</span>
        </h2>
        <p className="monitor__partner">
          <span>{partner.name}</span>
          <span className="monitor__locale">{`${partner.language} · ${partner.locale}`}</span>
        </p>
        <LedReadout text={time} label={`Match clock ${time}`} dotSize={2} />
      </header>
      <div className="monitor__frame">
        {/* The screen holds the stage, drawn as one image, and the notes about it, which stay
            readable as text. */}
        <div className="monitor__screen">
          <div
            className="monitor__stage"
            data-tenant={partner.id}
            role="img"
            aria-label={
              stageLabel ??
              `${partner.name} ${mode === "program" ? "on air now" : "preview"}: the rundown lists the same graphics`
            }
          >
            <Pitch />
            {program.score && (
              <ScoreBug
                item={program.score}
                // Program runs on the match clock; a preview stands outside time, so no time.
                clock={mode === "preview" ? null : clock ? time : undefined}
              />
            )}
            {program.strap ? (
              <CorrectionStrap key={program.strap.overlay.itemId} item={program.strap} />
            ) : (
              program.lowerThird && (
                <LowerThird key={program.lowerThird.overlay.itemId} item={program.lowerThird} />
              )
            )}
            {guides && (
              <div className="monitor__guides" aria-hidden="true">
                <span className="monitor__guide" data-area="action" />
                <span className="monitor__guide" data-area="title" />
              </div>
            )}
          </div>
          {mode === "preview" && program.lowerThird?.state === "pending_approval" && (
            <p className="monitor__held">Pending approval · held off air</p>
          )}
        </div>
      </div>
    </section>
  );
}
