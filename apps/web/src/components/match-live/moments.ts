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
import { MOMENT_LABELS } from "@/domain/moments";

interface MomentStyle {
  readonly label: string;
  readonly icon: LucideIcon;
}

/** How each kind of moment is named and marked on the wire. Icons, not colour: colour is state. */
export const MOMENT_STYLES: Record<Moment["kind"], MomentStyle> = {
  goal: { label: MOMENT_LABELS.goal, icon: CircleDot },
  big_chance: { label: MOMENT_LABELS.big_chance, icon: Crosshair },
  red_card: { label: MOMENT_LABELS.red_card, icon: RectangleVertical },
  var_overturn: { label: MOMENT_LABELS.var_overturn, icon: Undo2 },
  pressing_collapse: { label: MOMENT_LABELS.pressing_collapse, icon: TrendingDown },
  pressing_surge: { label: MOMENT_LABELS.pressing_surge, icon: TrendingUp },
  momentum_swing: { label: MOMENT_LABELS.momentum_swing, icon: Waves },
  tactical_shift: { label: MOMENT_LABELS.tactical_shift, icon: Waves },
};
