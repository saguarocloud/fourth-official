import type { Verdict } from "@/components/broadcast/verdict";
import { sealOf } from "@/domain/provenance";
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
    case "ready": {
      const seal = sealOf(lookup.answer);
      if (seal.tone === "failed") {
        return {
          tone: "red",
          text: `This record does not verify: ${seal.detail?.replace(/\.?$/, ".")}`,
        };
      }
      return seal.tone === "verified"
        ? { tone: "green", text: `${onRecord} for this match. This one is signed and unchanged.` }
        : {
            tone: "amber",
            text: `${onRecord} for this match. This one is unchanged but signed with a development key.`,
          };
    }
    case "missing":
      return { tone: "amber", text: `This item has no signed record yet. ${onRecord}.` };
    case "busy":
    case "unavailable":
      return { tone: "amber", text: `This record could not be read just now. ${onRecord}.` };
    default:
      return { tone: "neutral", text: `${onRecord} for this match. Reading the signed record.` };
  }
}
