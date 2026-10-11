import type { Verdict } from "@/components/broadcast/verdict";
import type { TenantItemEntry } from "@/contracts/feed";
import { formatMatchMinute } from "@/lib/format";

/** Where the match stands for its editors. */
export type Phase = "loading" | "unavailable" | "idle" | "running" | "finished" | "failed";

interface Standing {
  readonly phase: Phase;
  readonly waiting: readonly TenantItemEntry[];
  readonly decided: number;
}

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The one line an editor reads first: how much waits, and since when. */
export function approvalsVerdict({ phase, waiting, decided }: Standing): Verdict {
  if (phase === "unavailable") {
    return { tone: "red", text: "The match service is unavailable. Retrying every few seconds." };
  }
  if (phase === "loading") return { tone: "neutral", text: "Loading the matchday." };
  if (phase === "idle") {
    return {
      tone: "neutral",
      text: "This match has not started. Start the matchday from Match Live.",
    };
  }
  if (phase === "failed") {
    return { tone: "red", text: "This match's replay stopped. Held items stay off air." };
  }
  const oldest = waiting[0];
  const decisions = decided > 0 ? count(decided, "decision", "decisions") : "";
  if (phase === "finished") {
    return oldest
      ? {
          tone: "neutral",
          text: `Full time. ${count(waiting.length, "held item", "held items")} stayed off air.`,
        }
      : {
          tone: "neutral",
          text: `Full time. Nothing waits for an editor${decisions ? `; ${decisions} this match` : ""}.`,
        };
  }
  if (!oldest) {
    return {
      tone: decided > 0 ? "green" : "neutral",
      text: `Nothing waits for an editor.${decisions ? ` ${decisions} this match.` : ""}`,
    };
  }
  const since = formatMatchMinute(oldest.overlay.inAt.minute, oldest.overlay.inAt.period);
  return {
    tone: "amber",
    text: `${count(waiting.length, "item waits", "items wait")} for an editor; the oldest since ${since}.`,
  };
}
