import { RefreshCcw } from "lucide-react";

import { MOMENT_STYLES } from "@/components/match-live/moments";
import { AiTag } from "@/components/ui/AiTag";
import { PHASE_STATES } from "@/components/ui/phaseState";
import { StatusLamp, stateLabel } from "@/components/ui/StatusLamp";
import type { TenantItemEntry } from "@/contracts/feed";
import {
  type Partner,
  PARTNERS,
  type PartnerId,
  phaseAt,
  type RundownRow,
} from "@/domain/broadcast";
import { formatMatchMinute } from "@/lib/format";

interface RundownProps {
  readonly rows: readonly RundownRow[];
  readonly partner: PartnerId;
  readonly selected: string | null;
  readonly onSelect: (key: string) => void;
  /** Put a partner on the monitor: choosing a partner's cell previews that partner's version. */
  readonly onPartner?: (partner: PartnerId) => void;
  /** The match clock as an instant, so each graphic reads as queued, on air or published. */
  readonly now?: number | null;
}

function words(item: TenantItemEntry): string {
  return (
    item.rendered?.headline ??
    (item.overlay.content.template === "correction_strap" ? item.overlay.content.text : "")
  );
}

interface VersionProps {
  readonly item: TenantItemEntry | undefined;
  readonly partner: Partner;
  readonly now: number | null;
  readonly onChoose: () => void;
}

function Version({ item, partner, now, onChoose }: VersionProps) {
  if (!item) return <span className="rundown__none">Not sent</span>;
  const text = words(item);
  const state = PHASE_STATES[phaseAt(item, now)];
  const labelled = item.overlay.disclosure?.label ? ", AI-labelled" : "";
  return (
    <button
      type="button"
      className="rundown__pick"
      aria-label={`Preview ${partner.name}, ${stateLabel(state)}${labelled}: ${text}`}
      onClick={onChoose}
    >
      <span className="rundown__state">
        <StatusLamp state={state} />
        {item.overlay.disclosure?.label && <AiTag />}
      </span>
      <span className="rundown__words" lang={item.overlay.locale}>
        {text}
      </span>
    </button>
  );
}

function Kind({ row }: { row: RundownRow }) {
  const Icon = row.momentKind ? MOMENT_STYLES[row.momentKind].icon : RefreshCcw;
  return (
    <span className="rundown__label">
      <Icon aria-hidden="true" className="rundown__icon" strokeWidth={1.75} />
      {row.label}
    </span>
  );
}

/** The rundown: one row per moment and correction, each partner's version side by side. It is
 * the monitor's accessible equivalent: everything the monitor shows is here, as text. */
export function Rundown({
  rows,
  partner,
  selected,
  onSelect,
  onPartner,
  now = null,
}: RundownProps) {
  return (
    <section className="rundown" aria-labelledby="rundown-heading">
      <h2 id="rundown-heading" className="panel-heading">
        Rundown
      </h2>
      {rows.length === 0 ? (
        <p className="rundown__empty">
          No graphics yet. When the matchday runs, every moment explained and every correction
          appears here, with each partner&apos;s version side by side.
        </p>
      ) : (
        <table className="rundown__table" role="table">
          <caption className="sr-only">
            Each moment and correction, with every partner&apos;s version. Choose one to preview it.
          </caption>
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Moment</th>
              {PARTNERS.map((p) => (
                <th
                  key={p.id}
                  scope="col"
                  data-current={p.id === partner || undefined}
                  className="rundown__partner"
                >
                  <span aria-hidden="true">{p.code}</span>
                  <span className="sr-only">{p.name}</span>
                </th>
              ))}
            </tr>
          </thead>
          {/* Explicit roles: phones restyle the table as cards, and Safari then drops its
              semantics. */}
          <tbody role="rowgroup">
            {rows.map((row) => (
              <tr key={row.key} role="row" data-selected={row.key === selected || undefined}>
                <td className="rundown__time tabular" role="cell">
                  {formatMatchMinute(row.at.minute, row.at.period)}
                </td>
                <th scope="row" role="rowheader" className="rundown__moment">
                  <button
                    type="button"
                    className="rundown__pick"
                    aria-pressed={row.key === selected}
                    aria-label={`${row.label}, ${formatMatchMinute(row.at.minute, row.at.period)}: ${row.title}`}
                    onClick={() => onSelect(row.key)}
                  >
                    <Kind row={row} />
                    {row.kind === "correction" && (
                      <span className="rundown__title">{row.title}</span>
                    )}
                  </button>
                </th>
                {PARTNERS.map((p) => (
                  <td key={p.id} data-current={p.id === partner || undefined} data-partner={p.code}>
                    <Version
                      item={row.byPartner[p.id]}
                      partner={p}
                      now={now}
                      onChoose={() => {
                        onPartner?.(p.id);
                        onSelect(row.key);
                      }}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
