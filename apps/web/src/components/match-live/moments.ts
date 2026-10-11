import {
  CircleDot,
  Crosshair,
  RectangleVertical,
  TrendingDown,
  TrendingUp,
  Undo2,
  Waves,
  type LucideIcon,
} from "lucide-react";

import type { Moment } from "@/contracts/feed";

interface MomentStyle {
  readonly label: string;
  readonly icon: LucideIcon;
}

/** How each kind of moment is named and marked on the wire. Icons, not colour: colour is state. */
export const MOMENT_STYLES: Record<Moment["kind"], MomentStyle> = {
  goal: { label: "Goal", icon: CircleDot },
  big_chance: { label: "Big chance", icon: Crosshair },
  red_card: { label: "Red card", icon: RectangleVertical },
  var_overturn: { label: "VAR", icon: Undo2 },
  pressing_collapse: { label: "Press eases", icon: TrendingDown },
  pressing_surge: { label: "Press rises", icon: TrendingUp },
  momentum_swing: { label: "Momentum", icon: Waves },
  tactical_shift: { label: "Tactics", icon: Waves },
};
