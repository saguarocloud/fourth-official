/**
 * The Broadcast Preview's view model: every partner's items, folded in feed order. Pure and
 * deterministic, like the Match Live model, so a reconnecting stream lands on the same picture.
 *
 * One truth, three voices: the rundown has a row per moment explained (and per correction), and
 * each row holds every partner's version of it side by side.
 */
import type {
  ClockEntry,
  CorrectionEntry,
  FeedEntry,
  MatchClock,
  Moment,
  TenantItemEntry,
} from "@/contracts/feed";

import { MOMENT_LABELS } from "./moments";

export type PartnerId = "northlight-sport" | "tribuna-austral" | "rheinblick-sport";

export interface Partner {
  readonly id: PartnerId;
  readonly name: string;
  readonly code: string;
  readonly locale: "en-GB" | "es-MX" | "de-DE";
  readonly language: string;
  /** The keyboard key that switches the monitor to this partner. */
  readonly key: string;
}

/** The fictional broadcast partners, in the order their keys are numbered. */
export const PARTNERS: readonly Partner[] = [
  {
    id: "northlight-sport",
    name: "Northlight Sport",
    code: "NLS",
    locale: "en-GB",
    language: "English",
    key: "1",
  },
  {
    id: "tribuna-austral",
    name: "Tribuna Austral",
    code: "TRA",
    locale: "es-MX",
    language: "Spanish",
    key: "2",
  },
  {
    id: "rheinblick-sport",
    name: "Rheinblick Sport",
    code: "RHB",
    locale: "de-DE",
    language: "German",
    key: "3",
  },
];

export interface BroadcastState {
  readonly generation: number;
  /** The last entry applied; entries at or before it are ignored. */
  readonly lastSeq: number;
  readonly clock: ClockEntry | null;
  /** Every partner item, in the order the feed published them. */
  readonly items: readonly TenantItemEntry[];
  readonly moments: Readonly<Record<string, Moment>>;
  readonly corrections: readonly CorrectionEntry[];
}

export function emptyBroadcast(generation: number): BroadcastState {
  return { generation, lastSeq: 0, clock: null, items: [], moments: {}, corrections: [] };
}

/** Apply one entry. Entries at or before the last one applied are ignored, so replays are safe. */
export function applyBroadcast(state: BroadcastState, entry: FeedEntry): BroadcastState {
  if (entry.entrySeq <= state.lastSeq) return state;
  const next = { ...state, lastSeq: entry.entrySeq };
  switch (entry.kind) {
    case "clock":
      return { ...next, clock: entry };
    case "moment":
      return { ...next, moments: { ...state.moments, [entry.moment.momentId]: entry.moment } };
    case "correction":
      return { ...next, corrections: [...state.corrections, entry] };
    case "tenant_item":
      return { ...next, items: [...state.items, entry] };
    case "insight":
      return next;
  }
}

export function foldBroadcast(entries: readonly FeedEntry[], generation = 1): BroadcastState {
  return entries.reduce(applyBroadcast, emptyBroadcast(generation));
}

/** Seconds in one period's span of instants: above any match minute (minute 166 would reach it). */
const PERIOD_SPAN = 10_000;

/** A match clock as one comparable number: later is larger, across the break too. */
export function instant(clock: MatchClock): number {
  return clock.period * PERIOD_SPAN + clock.minute * 60 + clock.second;
}

export interface RundownRow {
  /** The canonical insight's id, or the correction's id. */
  readonly key: string;
  readonly kind: "insight" | "correction";
  /** When its earliest graphic comes in. */
  readonly at: MatchClock;
  /** The moment's kind ("Goal", "VAR"...), or "Correction". */
  readonly label: string;
  /** The moment's kind, for its icon; null for a correction. */
  readonly momentKind: Moment["kind"] | null;
  /** The canonical words: the English partner's headline, or what a correction changed. */
  readonly title: string;
  readonly byPartner: Readonly<Partial<Record<PartnerId, TenantItemEntry>>>;
}

function rowKey(item: TenantItemEntry): string | null {
  if (item.itemKind === "insight" || item.itemKind === "recap") {
    return item.localized?.insightId ?? null;
  }
  if (item.itemKind === "correction") {
    // A correction's item id is its partner's prefix and the correction id; anything else has
    // no row rather than a wrong one.
    const prefix = `it-${item.tenantId}-`;
    return item.overlay.itemId.startsWith(prefix) ? item.overlay.itemId.slice(prefix.length) : null;
  }
  return null; // the score bug has no row: the monitor always shows it
}

function title(items: readonly TenantItemEntry[], correction: CorrectionEntry | undefined): string {
  if (correction) return correction.summary;
  const english = items.find((i) => i.overlay.locale === "en-GB") ?? items[0];
  const content = english?.overlay.content;
  // Until the correction itself arrives, its strap says what changed.
  if (content?.template === "correction_strap") return content.text;
  return english?.rendered?.headline ?? "";
}

/** One row per moment explained and per correction, newest first. */
export function rundown(state: BroadcastState): RundownRow[] {
  const grouped = new Map<string, TenantItemEntry[]>();
  for (const item of state.items) {
    const key = rowKey(item);
    if (key !== null) grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }
  const rows: RundownRow[] = [...grouped].map(([key, items]) => {
    const isCorrection = items[0]?.itemKind === "correction";
    const correction = state.corrections.find((c) => c.correction.correctionId === key);
    const moment = items[0]?.localized ? state.moments[items[0].localized.momentId] : undefined;
    const at = items.map((i) => i.overlay.inAt).sort((a, b) => instant(a) - instant(b))[0]!;
    return {
      key,
      kind: isCorrection ? "correction" : "insight",
      at,
      label: isCorrection ? "Correction" : moment ? MOMENT_LABELS[moment.kind] : "Insight",
      momentKind: isCorrection ? null : (moment?.kind ?? null),
      title: title(items, correction),
      byPartner: Object.fromEntries(items.map((i) => [i.tenantId, i])),
    };
  });
  return rows.sort((a, b) => instant(b.at) - instant(a.at));
}

export interface Program {
  readonly lowerThird: TenantItemEntry | null;
  readonly strap: TenantItemEntry | null;
  readonly score: TenantItemEntry | null;
}

function latest(
  items: readonly TenantItemEntry[],
  partner: PartnerId,
  template: string,
  live: (item: TenantItemEntry) => boolean,
): TenantItemEntry | null {
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i]!;
    if (item.tenantId === partner && item.overlay.content.template === template && live(item)) {
      return item;
    }
  }
  return null;
}

/** Where a graphic stands at a match instant: waiting to come in, on air, or aired; an item held
 * for approval or rejected never airs. Without a clock, a graphic cleared for air is on air. */
export type Phase = "queued" | "airing" | "aired" | "held" | "rejected";

export function phaseAt(item: TenantItemEntry, now: number | null): Phase {
  if (item.state === "pending_approval") return "held";
  if (item.state === "rejected") return "rejected";
  if (now === null) return "airing";
  if (instant(item.overlay.inAt) > now) return "queued";
  return instant(item.overlay.outAt) < now ? "aired" : "airing";
}

/** What a partner has on air now: graphics between their in and out times on the match clock,
 * and the latest score that has come in on the bug. */
export function onAir(state: BroadcastState, partner: PartnerId): Program {
  const now = state.clock ? instant(state.clock.clock) : null;
  const airing = (item: TenantItemEntry) => phaseAt(item, now) === "airing";
  const inYet = (item: TenantItemEntry) => now === null || instant(item.overlay.inAt) <= now;
  return {
    lowerThird: latest(state.items, partner, "lower_third", airing),
    strap: latest(state.items, partner, "correction_strap", airing),
    score: latest(state.items, partner, "score_bug", inYet),
  };
}

/** A partner's version of one rundown row, whatever its state, with the score as it stands. */
export function preview(state: BroadcastState, partner: PartnerId, key: string): Program {
  const item = state.items.find((i) => i.tenantId === partner && rowKey(i) === key) ?? null;
  const template = item?.overlay.content.template;
  return {
    lowerThird: template === "lower_third" ? item : null,
    strap: template === "correction_strap" ? item : null,
    score: latest(state.items, partner, "score_bug", () => true),
  };
}
