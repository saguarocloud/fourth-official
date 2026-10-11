import { latestVersions } from "@/domain/approvals";
import { type BroadcastState, PARTNERS } from "@/domain/broadcast";
import type { RunState } from "@/domain/live";

export interface Verdict {
  readonly tone: "green" | "amber" | "red" | "neutral";
  readonly text: string;
}

const VOICES: Readonly<Record<number, string>> = { 2: "two", 3: "three", 4: "four" };

/** Who is holding items for approval: the partner by name when it is one, else how many. */
function holders(partners: ReadonlySet<string>): string {
  if (partners.size === 1) {
    const [only] = partners;
    return ` at ${PARTNERS.find((p) => p.id === only)?.name ?? only}`;
  }
  return ` across ${partners.size} partners`;
}

/** The one line a producer reads first: how many moments, what is cleared and what waits. */
export function verdictFor(state: BroadcastState, failed: boolean, run: RunState | null): Verdict {
  if (failed) {
    return { tone: "red", text: "The match service is unavailable. Retrying every few seconds." };
  }
  if (run === null) return { tone: "neutral", text: "Loading the matchday." };
  // Each partner's item as it stands now: a decision or a correction is its latest version.
  const narrative = latestVersions(state).filter((i) => i.itemKind === "insight");
  if (narrative.length === 0) {
    return run === "running"
      ? {
          tone: "neutral",
          text: "The match is under way. The first explained moment will appear here.",
        }
      : { tone: "neutral", text: "Nothing on the wire yet. Start the matchday from Match Live." };
  }
  const moments = new Set(narrative.map((i) => i.localized?.insightId)).size;
  const held = narrative.filter((i) => i.state === "pending_approval");
  const aired = narrative.filter((i) => i.state === "on_air").length;
  const pulled = narrative.filter((i) => i.state === "retracted").length;
  const corrected = pulled > 0 ? `; ${pulled} pulled by corrections` : "";
  const voices = `${moments} ${moments === 1 ? "moment" : "moments"} in ${VOICES[PARTNERS.length] ?? PARTNERS.length} voices`;
  if (held.length === 0) {
    return {
      tone: "green",
      text: `${voices}: ${aired} graphics cleared for air; nothing waits for an editor${corrected}.`,
    };
  }
  const waiting = holders(new Set(held.map((i) => i.tenantId)));
  return {
    tone: "amber",
    text: `${voices}: ${aired} graphics cleared for air, ${held.length} pending approval${waiting}${corrected}.`,
  };
}
