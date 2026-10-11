import type { Verdict } from "@/components/broadcast/verdict";
import type { Incident } from "@/domain/corrections";

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The one line a producer reads first: how many corrections, and what they reached. */
export function correctionsVerdict(
  incidents: readonly Incident[],
  failed: boolean,
  loading: boolean,
): Verdict {
  if (failed) {
    return { tone: "red", text: "The match service is unavailable. Retrying every few seconds." };
  }
  if (loading) return { tone: "neutral", text: "Loading the matchday." };
  if (incidents.length === 0) {
    return {
      tone: "neutral",
      text: "No corrections this match. When the source data changes, every item it reached appears here.",
    };
  }
  const actions = incidents.flatMap((i) => i.changes.map((c) => c.action));
  const partners = new Set(actions.map((a) => a.tenantId)).size;
  const languages = new Set(actions.map((a) => a.locale)).size;
  return {
    tone: "green",
    text: `${plural(incidents.length, "correction", "corrections")} this match: ${plural(actions.length, "partner item", "partner items")} corrected across ${plural(partners, "partner", "partners")} and ${plural(languages, "language", "languages")}.`,
  };
}
