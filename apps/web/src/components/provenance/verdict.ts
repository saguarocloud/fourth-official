import type { Verdict } from "@/components/broadcast/verdict";
import { plural } from "@/lib/plural";

import type { Lookup } from "./useProvenance";

/** The one line read first: whether the record on screen holds, or what stands in its way. */
export function provenanceVerdict(
  lookup: Lookup,
  items: number,
  failed: boolean,
  loading: boolean,
): Verdict {
  if (failed) {
    return { tone: "red", text: "The match service is unavailable. Retrying every few seconds." };
  }
  if (loading) return { tone: "neutral", text: "Loading the matchday." };
  if (items === 0) {
    return {
      tone: "neutral",
      text: "No partner item is on record for this match yet. Each one is signed as it is published.",
    };
  }
  const onRecord = `${plural(items, "partner item", "partner items")} on record`;
  switch (lookup.status) {
    case "ready":
      return lookup.answer.verification.valid
        ? {
            tone: "green",
            text: `This record is signed and unchanged. ${onRecord} for this match.`,
          }
        : {
            tone: "red",
            text: `This record does not verify: ${lookup.answer.verification.reason ?? "it could not be checked"}.`,
          };
    case "missing":
      return { tone: "amber", text: `This item has no signed record yet. ${onRecord}.` };
    case "busy":
    case "unavailable":
      return { tone: "amber", text: `This record could not be read just now. ${onRecord}.` };
    default:
      return { tone: "neutral", text: `${onRecord} for this match. Reading the signed record.` };
  }
}
