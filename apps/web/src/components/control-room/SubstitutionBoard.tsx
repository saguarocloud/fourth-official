import { LedReadout } from "@/components/led/LedReadout";
import type { Correction } from "@/domain/matchday";
import { formatLatency } from "@/lib/format";

interface SubstitutionBoardProps {
  readonly correction: Correction;
  readonly locale?: string;
}

/**
 * The fourth official's board, repurposed: what went out (red) and what replaced it (green).
 * Used wherever a correction is summarised.
 */
export function SubstitutionBoard({ correction, locale = "en-GB" }: SubstitutionBoardProps) {
  return (
    <figure className="sub-board">
      <div className="sub-board__panels">
        <div className="sub-board__panel" data-side="out">
          <span className="sub-board__label">Out</span>
          <LedReadout
            text={correction.published}
            label={`Published ${correction.published}`}
            tone="red"
            dotSize={4}
          />
        </div>
        <div className="sub-board__panel" data-side="in">
          <span className="sub-board__label">In</span>
          <LedReadout
            text={correction.corrected}
            label={`Corrected ${correction.corrected}`}
            tone="green"
            dotSize={4}
          />
        </div>
      </div>
      <figcaption className="sub-board__caption">
        <span>{correction.reason}</span>
        <span className="sub-board__impact">
          {`${correction.itemsCorrected} items · ${correction.partners} partners · ${correction.languages} languages · ${formatLatency(correction.elapsedMs, locale)}`}
        </span>
      </figcaption>
    </figure>
  );
}
