import { type ItemState, StatusLamp } from "@/components/ui/StatusLamp";
import type { TenantItemEntry } from "@/contracts/feed";
import { PARTNERS } from "@/domain/broadcast";
import type { ItemChange } from "@/domain/corrections";

const STATES: Readonly<Record<ItemChange["action"]["action"], ItemState>> = {
  retracted: "retracted",
  amended: "amended",
  escalated: "pending_approval",
};

function Words({ item, strike }: { item: TenantItemEntry; strike?: "red" | "violet" }) {
  return (
    <div className="change__words" data-strike={strike} lang={item.overlay.locale}>
      <p className="change__headline">{item.rendered?.headline}</p>
      <p className="change__line">{item.rendered?.claims[0]}</p>
    </div>
  );
}

function incoming(change: ItemChange): string {
  if (change.action.action === "escalated") return "Held for an editor: pending approval";
  return "Pulled off air";
}

/** One partner item a correction reached: what went out, and what came in. */
export function ChangeBoard({ change }: { change: ItemChange }) {
  const { action, before, after } = change;
  const partner = PARTNERS.find((p) => p.id === action.tenantId);
  const strike = action.action === "retracted" ? "red" : "violet";
  return (
    <li className="change">
      <header className="change__head">
        <span className="change__partner">{partner?.name ?? action.tenantId}</span>
        <span className="change__language">{partner?.language ?? action.locale}</span>
        <StatusLamp state={STATES[action.action]} />
        {action.was === "pending_approval" && (
          <span className="change__was">was held for an editor</span>
        )}
      </header>
      <div className="change__panels">
        <div className="change__panel" data-side="out" role="group" aria-label="Out">
          <span className="change__label" aria-hidden="true">
            Out
          </span>
          {before ? <Words item={before} strike={strike} /> : <p className="change__none">—</p>}
        </div>
        <div className="change__panel" data-side="in" role="group" aria-label="In">
          <span className="change__label" aria-hidden="true">
            In
          </span>
          {after ? (
            <>
              <Words item={after} />
              {action.action === "escalated" && <p className="change__note">{incoming(change)}</p>}
            </>
          ) : (
            <p className="change__none">{incoming(change)}</p>
          )}
        </div>
      </div>
    </li>
  );
}
