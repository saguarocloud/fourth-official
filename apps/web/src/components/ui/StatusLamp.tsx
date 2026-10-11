import {
  CircleCheck,
  CircleDashed,
  CircleSlash,
  Clock3,
  Hourglass,
  PenLine,
  Radio,
  type LucideIcon,
} from "lucide-react";

export const ITEM_STATES = [
  "on_air",
  "published",
  "pending_approval",
  "retracted",
  "amended",
  "dropped",
  "queued",
] as const;

export type ItemState = (typeof ITEM_STATES)[number];

interface StateStyle {
  readonly label: string;
  readonly tone: "red" | "green" | "amber" | "violet" | "muted";
  readonly icon: LucideIcon;
}

/** One colour, one icon and one label per state, used identically on every screen. */
const STATE_STYLES: Record<ItemState, StateStyle> = {
  on_air: { label: "On air", tone: "red", icon: Radio },
  published: { label: "Published", tone: "green", icon: CircleCheck },
  pending_approval: { label: "Pending approval", tone: "amber", icon: Hourglass },
  retracted: { label: "Retracted", tone: "red", icon: CircleSlash },
  amended: { label: "Amended", tone: "violet", icon: PenLine },
  dropped: { label: "Dropped", tone: "muted", icon: CircleDashed },
  queued: { label: "Queued", tone: "muted", icon: Clock3 },
};

interface StatusLampProps {
  readonly state: ItemState;
  /** Show only the lamp; the label stays available to screen readers. */
  readonly compact?: boolean;
}

/** The state's one label, for text that names it (an accessible name, say). */
export function stateLabel(state: ItemState): string {
  return STATE_STYLES[state].label;
}

export function StatusLamp({ state, compact = false }: StatusLampProps) {
  const { label, tone, icon: Icon } = STATE_STYLES[state];
  return (
    <span className="status-lamp" data-tone={tone} data-state={state}>
      <Icon aria-hidden="true" className="status-lamp__icon" strokeWidth={1.75} />
      <span className={compact ? "sr-only" : "status-lamp__label"}>{label}</span>
    </span>
  );
}
