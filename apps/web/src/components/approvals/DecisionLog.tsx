import { type ItemState, StatusLamp } from "@/components/ui/StatusLamp";
import type { DecidedItem } from "@/domain/approvals";
import { PARTNERS, type Phase, phaseAt } from "@/domain/broadcast";

const NOW: Record<Phase, ItemState> = {
  queued: "queued",
  airing: "on_air",
  aired: "published",
  held: "pending_approval",
  rejected: "dropped",
};

// The studio's clock: the time in the top bar, so the log and the clock agree.
const STUDIO_TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function timeOf(iso: string): string {
  const at = new Date(iso);
  return Number.isNaN(at.getTime()) ? "" : STUDIO_TIME.format(at);
}

interface DecisionLogProps {
  readonly items: readonly DecidedItem[];
  readonly now: number | null;
}

/** What editors decided this match, newest first, with who and why: the audit trail. */
export function DecisionLog({ items, now }: DecisionLogProps) {
  return (
    <section className="decision-log" aria-labelledby="decisions-heading">
      <h2 id="decisions-heading" className="panel-heading">
        Decisions
      </h2>
      {items.length === 0 ? (
        <p className="decision-log__empty">No decisions yet this match.</p>
      ) : (
        <table className="decision-log__table" role="table" aria-labelledby="decisions-heading">
          <thead>
            <tr>
              <th scope="col">Decided (studio time)</th>
              <th scope="col">Partner</th>
              <th scope="col">Item</th>
              <th scope="col">Decision</th>
              <th scope="col">Now</th>
              <th scope="col">Editor</th>
              <th scope="col">Reason</th>
            </tr>
          </thead>
          {/* Explicit roles: phones restyle the table as cards, and Safari then drops its
              semantics. */}
          <tbody role="rowgroup">
            {items.map((item) => {
              const { approval } = item;
              return (
                <tr key={`${item.tenantId}/${item.overlay.itemId}`} role="row">
                  <td role="cell" data-label="Decided" className="tabular">
                    {timeOf(approval.decidedAt)}
                  </td>
                  <td role="cell" data-label="Partner">
                    {PARTNERS.find((p) => p.id === item.tenantId)?.name ?? item.tenantId}
                  </td>
                  <td role="cell" data-label="Item" lang={item.overlay.locale}>
                    {item.rendered?.headline}
                  </td>
                  <td role="cell" data-label="Decision">
                    {approval.decision === "approved" ? "Approved" : "Rejected"}
                  </td>
                  <td role="cell" data-label="Now">
                    <StatusLamp state={NOW[phaseAt(item, now)]} />
                  </td>
                  <td role="cell" data-label="Editor">
                    <span>
                      {approval.editor}
                      <span className="decision-log__role"> · duty editor (demo identity)</span>
                    </span>
                  </td>
                  <td role="cell" data-label="Reason">
                    {approval.reason ?? ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
