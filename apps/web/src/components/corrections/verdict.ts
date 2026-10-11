import type { Verdict } from "@/components/broadcast/verdict";
import type { Incident } from "@/domain/corrections";
import { plural } from "@/lib/plural";

/** The one line a producer reads first: how many corrections, what they reached, and anything
 * still waiting for an editor. */
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
  const held = actions.filter((a) => a.action === "escalated").length;
  const waiting =
    held > 0 ? `; ${plural(held, "new version", "new versions")} held for an editor` : "";
  return {
    tone: held > 0 ? "amber" : "green",
    text: `${plural(incidents.length, "correction", "corrections")} this match: ${plural(actions.length, "partner item", "partner items")} corrected across ${plural(partners, "partner", "partners")} and ${plural(languages, "language", "languages")}${waiting}.`,
  };
}
