import { LedReadout } from "@/components/led/LedReadout";
import type { CorrectionEntry } from "@/contracts/feed";

interface CorrectionBoardProps {
  readonly correction: CorrectionEntry;
  /** How many items already published the correction reached. */
  readonly itemsCorrected: number;
  readonly locale?: string;
  /** Where the corrected item is on the page, when it is shown. */
  readonly href?: string;
}

/** A correction on the fourth official's board: what went out (red) and what came in (green). */
export function CorrectionBoard({
  correction,
  itemsCorrected,
  locale = "en-GB",
  href,
}: CorrectionBoardProps) {
  const issued = new Date(correction.correction.issuedAt).toLocaleTimeString(locale, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
  });
  return (
    <figure className="sub-board">
      <div className="sub-board__panels">
        <div className="sub-board__panel" data-side="out">
          <span className="sub-board__label">Out</span>
          <LedReadout
            text={correction.outText}
            label={`Out: ${correction.outText}`}
            tone="red"
            dotSize={4}
          />
        </div>
        <div className="sub-board__panel" data-side="in">
          <span className="sub-board__label">In</span>
          <LedReadout
            text={correction.inText}
            label={`In: ${correction.inText}`}
            tone="green"
            dotSize={4}
          />
        </div>
      </div>
      <figcaption className="sub-board__caption">
        {href ? (
          <a className="sub-board__summary" href={href}>
            {correction.summary}
          </a>
        ) : (
          <span className="sub-board__summary">{correction.summary}</span>
        )}
        <span className="sub-board__impact">
          {itemsCorrected === 0
            ? "No published item rested on it."
            : `${itemsCorrected} published ${itemsCorrected === 1 ? "item" : "items"} corrected.`}
        </span>
        <span className="sub-board__when tabular">{`Issued ${issued} UTC`}</span>
      </figcaption>
    </figure>
  );
}
