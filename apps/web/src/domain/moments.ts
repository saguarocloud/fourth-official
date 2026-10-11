import type { Moment } from "@/contracts/feed";

/** What each kind of moment is called, on every screen. */
export const MOMENT_LABELS: Record<Moment["kind"], string> = {
  goal: "Goal",
  big_chance: "Big chance",
  red_card: "Red card",
  var_overturn: "VAR",
  pressing_collapse: "Press eases",
  pressing_surge: "Press rises",
  momentum_swing: "Momentum",
  tactical_shift: "Tactics",
};
