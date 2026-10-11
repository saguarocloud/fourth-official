import type { Phase } from "@/domain/broadcast";

import type { ItemState } from "./StatusLamp";

/** The shared lamp for where a partner's graphic stands, on every screen that lists them. */
export const PHASE_STATES: Readonly<Record<Phase, ItemState>> = {
  queued: "queued",
  airing: "on_air",
  aired: "published",
  held: "pending_approval",
  rejected: "dropped",
  retracted: "retracted",
  amended: "amended",
};
