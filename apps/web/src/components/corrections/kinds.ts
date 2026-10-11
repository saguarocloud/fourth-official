import type { CorrectionEntry } from "@/contracts/feed";

type Kind = CorrectionEntry["correction"]["kind"];

/** What a correction did to its event, as the screen names it. */
export const KIND_NAMES: Readonly<Record<Kind, { readonly key: string; readonly fact: string }>> = {
  EVENT_VOIDED: { key: "Ruled out", fact: "Event voided" },
  EVENT_AMENDED: { key: "Amended", fact: "Event amended" },
};

/** How long the desk took: milliseconds under a second, as it almost always is. */
export function deskTime(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}
