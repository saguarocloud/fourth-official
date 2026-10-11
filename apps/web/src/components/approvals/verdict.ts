import type { Verdict } from "@/components/broadcast/verdict";
import type { TenantItemEntry } from "@/contracts/feed";
import { formatMatchMinute } from "@/lib/format";

interface Standing {
  readonly failed: boolean;
  readonly loading: boolean;
  readonly closed: boolean;
  readonly waiting: readonly TenantItemEntry[];
  readonly decided: number;
}

/** The one line an editor reads first: how much waits, and since when. */
export function approvalsVerdict({ failed, loading, closed, waiting, decided }: Standing): Verdict {
  if (failed) {
    return { tone: "red", text: "The match service is unavailable. Retrying every few seconds." };
  }
  if (loading) return { tone: "neutral", text: "Loading the matchday." };
  const held = waiting.length;
  if (held === 0) {
    const done =
      decided > 0 ? ` ${decided} ${decided === 1 ? "decision" : "decisions"} this match.` : "";
    return { tone: decided > 0 ? "green" : "neutral", text: `Nothing waits for an editor.${done}` };
  }
  if (closed) {
    return {
      tone: "neutral",
      text: `Full time. ${held} held ${held === 1 ? "item" : "items"} stayed off air.`,
    };
  }
  const oldest = waiting[0]!.overlay.inAt;
  return {
    tone: "amber",
    text: `${held} ${held === 1 ? "item waits" : "items wait"} for an editor; the oldest since ${formatMatchMinute(oldest.minute, oldest.period)}.`,
  };
}
