import { CircleAlert, CircleCheck, History } from "lucide-react";

import { LiveClock } from "@/components/shell/LiveClock";
import { BrandMark } from "@/components/shell/BrandMark";
import type { MatchdaySummary } from "@/domain/matchday";
import { formatCost, formatLatency } from "@/lib/format";

interface TopBarProps {
  readonly summary: MatchdaySummary;
  readonly studio: string;
  /** True while the screen shows a replayed synthetic matchday rather than live data. */
  readonly replay: boolean;
  readonly locale?: string;
}

export function TopBar({ summary, studio, replay, locale = "en-GB" }: TopBarProps) {
  return (
    <header className="top-bar">
      <div className="top-bar__identity">
        <BrandMark />
        <div className="top-bar__names">
          <span className="top-bar__product">Fourth Official</span>
          <span className="top-bar__studio">{studio}</span>
        </div>
      </div>

      {replay && (
        <span className="top-bar__replay">
          <History aria-hidden="true" strokeWidth={1.75} />
          <span>
            Replay<span className="top-bar__replay-detail"> · synthetic matchday</span>
          </span>
        </span>
      )}

      <dl className="top-bar__readouts">
        <div data-breach={!summary.withinSlo || undefined}>
          <dt>Event to air, p95</dt>
          <dd>
            {summary.withinSlo ? (
              <CircleCheck aria-hidden="true" strokeWidth={1.75} />
            ) : (
              <CircleAlert aria-hidden="true" strokeWidth={1.75} />
            )}
            <span>{formatLatency(summary.p95LatencyMs, locale)}</span>
            <span className="top-bar__slo">{summary.withinSlo ? "Within SLO" : "Outside SLO"}</span>
          </dd>
        </div>
        <div data-attention={summary.pendingApprovals > 0 || undefined}>
          <dt>Pending approvals</dt>
          <dd>{summary.pendingApprovals}</dd>
        </div>
        <div data-attention={summary.corrections > 0 || undefined}>
          <dt>Corrections</dt>
          <dd>{summary.corrections}</dd>
        </div>
        <div>
          <dt>Cost so far</dt>
          <dd>{formatCost(summary.costCents, locale)}</dd>
        </div>
      </dl>

      <LiveClock />
    </header>
  );
}
