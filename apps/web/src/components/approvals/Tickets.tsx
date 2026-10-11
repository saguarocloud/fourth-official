import { MOMENT_STYLES } from "@/components/match-live/moments";
import type { Moment, TenantItemEntry } from "@/contracts/feed";
import { PARTNERS } from "@/domain/broadcast";
import { formatMatchMinute } from "@/lib/format";

export function ticketKey(item: TenantItemEntry): string {
  return `${item.tenantId}/${item.overlay.itemId}`;
}

interface TicketsProps {
  readonly items: readonly TenantItemEntry[];
  readonly moments: Readonly<Record<string, Moment>>;
  readonly current: string | null;
  readonly onChoose: (key: string) => void;
  readonly onMove: (by: number) => void;
  /** Full time: nothing more will be held this match. */
  readonly closed: boolean;
}

/** What waits for an editor, oldest first: one ticket per item, the one on the desk pressed. */
export function Tickets({ items, moments, current, onChoose, onMove, closed }: TicketsProps) {
  const at = items.findIndex((i) => ticketKey(i) === current);
  return (
    <section className="tickets" aria-labelledby="tickets-heading">
      <div className="tickets__head">
        <h2 id="tickets-heading" className="panel-heading" tabIndex={-1}>
          Waiting <span className="tickets__count tabular">{items.length}</span>
        </h2>
        {items.length > 1 && (
          <div className="tickets__move">
            <button
              type="button"
              className="key"
              data-size="sm"
              aria-keyshortcuts="K"
              disabled={at <= 0}
              onClick={() => onMove(-1)}
            >
              <span>
                <span className="key-cap" aria-hidden="true">
                  K
                </span>
                Previous
              </span>
            </button>
            <button
              type="button"
              className="key"
              data-size="sm"
              aria-keyshortcuts="J"
              disabled={at >= items.length - 1}
              onClick={() => onMove(1)}
            >
              <span>
                <span className="key-cap" aria-hidden="true">
                  J
                </span>
                Next
              </span>
            </button>
          </div>
        )}
      </div>
      {items.length === 0 ? (
        <p className="tickets__empty">
          {closed
            ? "Full time. Nothing more will be held this match."
            : "Nothing waits. Items a partner's policy holds for an editor appear here as the match runs."}
        </p>
      ) : (
        <ul className="tickets__list" aria-label="Waiting">
          {items.map((item) => {
            const key = ticketKey(item);
            const partner = PARTNERS.find((p) => p.id === item.tenantId);
            const kind = item.localized ? moments[item.localized.momentId]?.kind : undefined;
            const style = kind ? MOMENT_STYLES[kind] : undefined;
            const Icon = style?.icon;
            return (
              <li key={key}>
                <button
                  type="button"
                  className="ticket"
                  aria-current={key === current}
                  onClick={() => onChoose(key)}
                >
                  <span className="ticket__head">
                    <span className="ticket__code">{partner?.code ?? item.tenantId}</span>
                    <span className="ticket__kind">
                      {Icon && (
                        <Icon aria-hidden="true" className="ticket__icon" strokeWidth={1.75} />
                      )}
                      {style?.label ?? "Insight"}
                    </span>
                    <span className="ticket__since tabular">
                      {formatMatchMinute(item.overlay.inAt.minute, item.overlay.inAt.period)}
                    </span>
                  </span>
                  <span className="ticket__words" lang={item.overlay.locale}>
                    {item.rendered?.headline}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
