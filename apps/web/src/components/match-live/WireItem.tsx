import { ChevronRight, LoaderCircle } from "lucide-react";

import { AiTag } from "@/components/ui/AiTag";
import type { AttemptRecord, InsightEntry } from "@/contracts/feed";
import { StatusLamp } from "@/components/ui/StatusLamp";
import { itemState, type LiveItem } from "@/domain/live";
import { formatMatchMinute } from "@/lib/format";

import { MOMENT_STYLES } from "./moments";

interface WireItemProps {
  readonly item: LiveItem;
}

function attemptText(attempt: AttemptRecord): string {
  if (attempt.outcome === "passed") return "passed every check";
  if (attempt.outcome === "error") return `model error (${attempt.error ?? "unknown"})`;
  return `refused: ${attempt.findings.join(", ").replaceAll("_", " ").toLowerCase()}`;
}

/** How the insight was verified: the model and prompt that wrote it, or the template, and every
 * attempt the Verifier judged on the way. */
function Provenance({ insight }: { insight: InsightEntry }) {
  const { attempts, insight: written } = insight;
  const models = attempts.filter((a) => a.model !== "none").length;
  const summary =
    written.provenance.producedBy === "template"
      ? models === 0
        ? "Deterministic template, no model"
        : `Deterministic template after ${models} model ${models === 1 ? "attempt" : "attempts"}`
      : `Verified on attempt ${attempts.length} · model ${written.provenance.model} · prompt ${written.provenance.promptVersion}`;
  return (
    <details className="wire-item__provenance">
      <summary>
        <ChevronRight aria-hidden="true" strokeWidth={1.75} className="wire-item__chevron" />
        {summary}
      </summary>
      <ol>
        {attempts.map((attempt) => (
          <li key={attempt.number} data-outcome={attempt.outcome}>
            <span className="tabular">{attempt.number}</span>
            <span>{attempt.model === "none" ? "template" : attempt.model}</span>
            <span>{attemptText(attempt)}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

/** One moment on the wire: when, what, the verified insight, and anything that corrected it. */
export function WireItem({ item }: WireItemProps) {
  const { moment, insight, correction } = item;
  const state = itemState(item);
  const style = MOMENT_STYLES[moment.kind];
  const Icon = style.icon;
  const minute = formatMatchMinute(moment.clock.minute, moment.clock.period);
  const modelWritten = insight?.insight.provenance.producedBy === "model";
  const headingId = `moment-${moment.momentId}`;

  return (
    <li className="wire-item" data-state={state} aria-labelledby={headingId}>
      <div className="wire-item__when">
        <span className="wire-item__minute tabular">{minute}</span>
        <span className="wire-item__kind">
          <Icon aria-hidden="true" strokeWidth={1.75} />
          {style.label}
        </span>
      </div>
      <div className="wire-item__body">
        <h3
          id={headingId}
          className={
            insight === null
              ? "wire-item__headline wire-item__headline--pending"
              : "wire-item__headline"
          }
        >
          {insight === null ? `${style.label} detected` : insight.rendered.headline}
        </h3>
        {correction !== null && (
          <p className="wire-item__correction" data-kind={correction.correction.kind}>
            <span className="wire-item__correction-label">
              {state === "retracted" ? "Retracted" : "Corrected"}
            </span>
            {correction.summary}
          </p>
        )}
        {insight === null ? (
          <p className="wire-item__meta">
            <span className="wire-item__verifying">
              <LoaderCircle aria-hidden="true" strokeWidth={1.75} />
              Explaining and verifying
            </span>
          </p>
        ) : (
          <>
            {state === "amended" && <p className="wire-item__superseded-label">As published</p>}
            <ul className="wire-item__claims" data-superseded={state === "amended" || undefined}>
              {insight.rendered.claims.map((claim, index) => (
                <li key={`${insight.insight.insightId}-${index}`}>{claim}</li>
              ))}
            </ul>
            <div className="wire-item__meta">
              {/* A correction strap already names the state; the lamp would repeat it. */}
              {state === "published" && <StatusLamp state={state} />}
              {modelWritten && <AiTag />}
              <Provenance insight={insight} />
            </div>
          </>
        )}
      </div>
    </li>
  );
}
