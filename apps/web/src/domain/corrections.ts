/**
 * The Corrections Center's view of a match: one incident per correction, with every report the
 * corrections desk published for it merged (a correction is reported when issued, and again when
 * partner items that rest on it arrive later; ADR-012).
 */
import type {
  CorrectionAction,
  CorrectionEntry,
  CorrectionReportEntry,
  TenantItemEntry,
} from "@/contracts/feed";
import { formatMatchMinute } from "@/lib/format";

import type { BroadcastState } from "./broadcast";
import { MOMENT_LABELS } from "./moments";

/** One partner item a correction reached: the version that went out, and what came in. */
export interface ItemChange {
  readonly action: CorrectionAction;
  /** The version as it was when the desk acted: on air or held. */
  readonly before: TenantItemEntry | null;
  /** The new version, for an amendment or an escalation; null when the item was pulled. */
  readonly after: TenantItemEntry | null;
}

/** A canonical insight a correction reached, named as a producer would: "Goal 89'". */
export interface InsightReached {
  readonly id: string;
  readonly label: string;
}

export interface Incident {
  readonly correction: CorrectionEntry;
  readonly reports: readonly CorrectionReportEntry[];
  readonly insights: readonly InsightReached[];
  readonly changes: readonly ItemChange[];
  /** The desk's working time, summed over its reports. */
  readonly elapsedMs: number;
  readonly items: number;
  /** Of those items, how many were on air (the rest were held for an editor). */
  readonly onAir: number;
  readonly partners: number;
  readonly languages: number;
}

function byItem(items: readonly TenantItemEntry[]): Map<string, TenantItemEntry[]> {
  const versions = new Map<string, TenantItemEntry[]>();
  for (const item of items) {
    versions.set(item.overlay.itemId, [...(versions.get(item.overlay.itemId) ?? []), item]);
  }
  return versions;
}

function labelOf(state: BroadcastState, insightId: string): string {
  const item = state.items.find((i) => i.localized?.insightId === insightId);
  const moment = item?.localized ? state.moments[item.localized.momentId] : undefined;
  if (moment === undefined) return "Insight";
  return `${MOMENT_LABELS[moment.kind]} ${formatMatchMinute(moment.clock.minute, moment.clock.period)}`;
}

function changesOf(
  versions: Map<string, TenantItemEntry[]>,
  reports: readonly CorrectionReportEntry[],
): ItemChange[] {
  // An item named again by a later report keeps its last action, once.
  const last = new Map<string, { action: CorrectionAction; seq: number }>();
  for (const report of reports) {
    for (const action of report.actions) {
      last.set(action.itemId, { action, seq: report.entrySeq });
    }
  }
  return [...last.values()].map(({ action, seq }) => {
    const all = versions.get(action.itemId) ?? [];
    const before = all.filter((i) => i.entrySeq < seq && i.state === action.was).at(-1) ?? null;
    const after = action.newItemId ? (versions.get(action.newItemId)?.at(-1) ?? null) : null;
    return { action, before, after };
  });
}

/** Every correction issued this match, in order, each with what the desk did about it. */
export function incidents(state: BroadcastState): Incident[] {
  const versions = byItem(state.items);
  return state.corrections.map((correction) => {
    const id = correction.correction.correctionId;
    const reports = state.reports.filter((r) => r.correctionId === id);
    const changes = changesOf(versions, reports);
    const actions = changes.map((c) => c.action);
    // Every insight a report lists or an action names, so no action hangs without its insight.
    const ids = [
      ...new Set([...reports.flatMap((r) => r.insightIds), ...actions.map((a) => a.insightId)]),
    ];
    return {
      correction,
      reports,
      insights: ids.map((insightId) => ({ id: insightId, label: labelOf(state, insightId) })),
      changes,
      elapsedMs: reports.reduce((sum, r) => sum + r.elapsedMs, 0),
      items: actions.length,
      onAir: actions.filter((a) => a.was === "on_air").length,
      partners: new Set(actions.map((a) => a.tenantId)).size,
      languages: new Set(actions.map((a) => a.locale)).size,
    };
  });
}

/** The incident to open on: the one that reached the most items, the earliest on a tie. */
export function leading(all: readonly Incident[]): Incident | null {
  return all.reduce<Incident | null>(
    (best, i) => (best === null || i.items > best.items ? i : best),
    null,
  );
}
