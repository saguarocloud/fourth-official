import { type ItemState, StatusLamp } from "@/components/ui/StatusLamp";
import type { TenantItemEntry } from "@/contracts/feed";
import { PARTNERS } from "@/domain/broadcast";
import type { ItemChange } from "@/domain/corrections";

const STATES: Readonly<Record<ItemChange["action"]["action"], ItemState>> = {
  retracted: "retracted",
  amended: "amended",
  escalated: "pending_approval",
};

function Words({ item, struck }: { item: TenantItemEntry; struck?: "red" | "violet" }) {
  if (item.rendered === null) return <p className="change__none">Its words are not on the feed.</p>;
  return (
    <div className="change__words" data-strike={struck} lang={item.overlay.locale}>
      <p className="change__headline">{item.rendered.headline}</p>
      <p className="change__line">{item.rendered.claims[0] ?? ""}</p>
      {struck && <span className="sr-only">{struck === "red" ? "(withdrawn)" : "(replaced)"}</span>}
    </div>
  );
}

/** What took the old version's place, in words. */
function incoming({ action, after }: ItemChange): string {
  if (action.action === "escalated") return "Held for an editor: pending approval";
  if (action.action === "amended") return after ? "" : "The new version is not on the feed yet";
  return action.was === "pending_approval" ? "Withdrawn before air" : "Pulled off air";
}

/** One partner item a correction reached: what went out, and what came in. */
export function ChangeBoard({ change, first }: { change: ItemChange; first: boolean }) {
  const { action, before, after } = change;
  const partner = PARTNERS.find((p) => p.id === action.tenantId);
  const name = partner?.name ?? action.tenantId;
  const struck = action.action === "retracted" ? "red" : "violet";
  const note = incoming(change);
  return (
    <li className="change">
      <header className="change__head">
        <h3
          className="change__partner"
          id={first ? "first-change" : undefined}
          tabIndex={first ? -1 : undefined}
        >
          {name}
        </h3>
        <span className="change__language">{partner?.language ?? action.locale}</span>
        <StatusLamp state={STATES[action.action]} />
        {action.was === "pending_approval" && (
          <span className="change__was">was held for an editor</span>
        )}
      </header>
      <div className="change__panels">
        <div className="change__panel" data-side="out" role="group" aria-label={`Out: ${name}`}>
          <span className="change__label" aria-hidden="true">
            Out
          </span>
          {before ? <Words item={before} struck={struck} /> : <p className="change__none">—</p>}
        </div>
        <div className="change__panel" data-side="in" role="group" aria-label={`In: ${name}`}>
          <span className="change__label" aria-hidden="true">
            In
          </span>
          {after && <Words item={after} />}
          {note && <p className={after ? "change__note" : "change__none"}>{note}</p>}
        </div>
      </div>
    </li>
  );
}
