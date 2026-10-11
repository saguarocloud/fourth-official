/**
 * The Match Live view model: feed entries folded, in order, into what the screen shows. Pure and
 * deterministic, so a reconnecting stream or a page reload always lands on the same picture.
 */
import type {
  ClockEntry,
  CorrectionEntry,
  FeedEntry,
  InsightEntry,
  Moment,
} from "@/contracts/feed";

/** What is happening to a moment's insight. Published, retracted and amended are item states. */
export type ItemStatus = "drafting" | "published" | "retracted" | "amended";

export interface LiveItem {
  readonly moment: Moment;
  readonly insight: InsightEntry | null;
  /** The correction that changed this item, if one did. */
  readonly correction: CorrectionEntry | null;
}

export interface LiveMatch {
  readonly generation: number;
  /** The last entry applied; entries at or before it are ignored. */
  readonly lastSeq: number;
  readonly clock: ClockEntry | null;
  /** Newest moment first. */
  readonly items: readonly LiveItem[];
  readonly corrections: readonly CorrectionEntry[];
}

export type RunState = "idle" | "running" | "finished" | "failed";

export function emptyLive(generation: number): LiveMatch {
  return { generation, lastSeq: 0, clock: null, items: [], corrections: [] };
}

function evidenceOf(item: LiveItem): Set<string> {
  const cited = new Set(item.moment.eventIds);
  for (const claim of item.insight?.insight.claims ?? []) {
    claim.evidence.eventIds.forEach((id) => cited.add(id));
  }
  return cited;
}

/** A correction touches every item resting on the event it corrects, except the VAR overturn
 * that explains that very void. */
function touches(item: LiveItem, correction: CorrectionEntry): boolean {
  const { kind, targetEventId } = correction.correction;
  if (kind === "EVENT_VOIDED" && item.moment.kind === "var_overturn") return false;
  return evidenceOf(item).has(targetEventId);
}

function withCorrections(item: LiveItem, corrections: readonly CorrectionEntry[]): LiveItem {
  const latest = [...corrections].reverse().find((c) => touches(item, c)) ?? null;
  return latest === item.correction ? item : { ...item, correction: latest };
}

export function itemState(item: LiveItem): ItemStatus {
  if (item.insight === null) return "drafting";
  if (item.correction === null) return "published";
  return item.correction.correction.kind === "EVENT_VOIDED" ? "retracted" : "amended";
}

/** Apply one entry. Entries at or before the last one applied are ignored, so replays are safe. */
export function applyEntry(live: LiveMatch, entry: FeedEntry): LiveMatch {
  if (entry.entrySeq <= live.lastSeq) return live;
  const next = { ...live, lastSeq: entry.entrySeq };
  switch (entry.kind) {
    case "clock":
      return { ...next, clock: entry };
    case "moment": {
      const item = withCorrections(
        { moment: entry.moment, insight: null, correction: null },
        live.corrections,
      );
      const items = [item, ...live.items].sort((a, b) => b.moment.asOfSeq - a.moment.asOfSeq);
      return { ...next, items };
    }
    case "insight":
      return {
        ...next,
        items: live.items.map((item) =>
          item.moment.momentId === entry.insight.momentId
            ? withCorrections({ ...item, insight: entry }, live.corrections)
            : item,
        ),
      };
    case "correction": {
      const corrections = [...live.corrections, entry];
      return {
        ...next,
        corrections,
        items: live.items.map((item) => withCorrections(item, corrections)),
      };
    }
    case "tenant_item":
      // A partner's graphic: shown by the Broadcast Preview, not here.
      return next;
  }
}

export function foldFeed(entries: readonly FeedEntry[], generation = 1): LiveMatch {
  return entries.reduce(applyEntry, emptyLive(generation));
}

const KINDS = new Set(["clock", "moment", "insight", "correction"]);

/** A feed entry from the stream, or null if it is not one for this match. The server is ours and
 * validates everything it sends; this guards the shape the reducer relies on. */
export function parseEntry(raw: string, matchId: string): FeedEntry | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const entry = value as Record<string, unknown>;
  if (entry.matchId !== matchId || !KINDS.has(String(entry.kind))) return null;
  if (typeof entry.entrySeq !== "number" || !Number.isInteger(entry.entrySeq)) return null;
  return value as FeedEntry;
}

export interface Verdict {
  readonly tone: "green" | "amber" | "red";
  readonly text: string;
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** The screen's one-line verdict, readable in five seconds. */
export function liveVerdict(live: LiveMatch, state: RunState): Verdict {
  const insights = live.items.filter((item) => item.insight !== null).length;
  const verified = plural(insights, "verified insight", "verified insights");
  if (state === "failed") {
    return {
      tone: "red",
      text: "The replay stopped unexpectedly. Start the matchday again to retry.",
    };
  }
  if (state === "idle" && live.lastSeq === 0) {
    return { tone: "amber", text: "No replay is running. Start the matchday to watch it unfold." };
  }
  if (state === "finished") {
    const corrections = live.corrections.length;
    const reached =
      corrections === 0
        ? "."
        : `; ${plural(corrections, "correction", "corrections")} reached every item they touched.`;
    return { tone: "green", text: `Full time. ${verified}${reached}` };
  }
  const drafting = live.items.length - insights;
  const pending = drafting > 0 ? `, ${drafting} being verified` : "";
  return { tone: "green", text: `Live. ${verified} so far${pending}.` };
}
