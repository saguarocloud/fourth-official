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

import type { BroadcastState } from "./broadcast";

/** One partner item a correction reached: the version that went out, and what came in. */
export interface ItemChange {
  readonly action: CorrectionAction;
  /** The version as it was when the correction arrived: on air or held. */
  readonly before: TenantItemEntry | null;
  /** The new version, for an amendment or an escalation; null when the item was pulled. */
  readonly after: TenantItemEntry | null;
}

export interface Incident {
  readonly correction: CorrectionEntry;
  readonly reports: readonly CorrectionReportEntry[];
  readonly insightIds: readonly string[];
  readonly changes: readonly ItemChange[];
  /** The desk's working time across its reports, and when it first started. */
  readonly elapsedMs: number;
  readonly startedAt: string | null;
  readonly items: number;
  readonly partners: number;
  readonly languages: number;
}

function versionOf(
  items: readonly TenantItemEntry[],
  itemId: string,
  matches: (item: TenantItemEntry) => boolean,
): TenantItemEntry | null {
  for (let i = items.length - 1; i >= 0; i -= 1) {
    const item = items[i]!;
    if (item.overlay.itemId === itemId && matches(item)) return item;
  }
  return null;
}

function changeOf(state: BroadcastState, action: CorrectionAction): ItemChange {
  return {
    action,
    before: versionOf(state.items, action.itemId, (i) => i.state === action.was),
    after:
      action.newItemId === null || action.newItemId === undefined
        ? null
        : versionOf(state.items, action.newItemId, () => true),
  };
}

/** Every correction issued this match, in order, each with what the desk did about it. */
export function incidents(state: BroadcastState): Incident[] {
  return state.corrections.map((correction) => {
    const id = correction.correction.correctionId;
    const reports = state.reports.filter((r) => r.correctionId === id);
    const actions = reports.flatMap((r) => r.actions);
    const changes = actions.map((a) => changeOf(state, a));
    return {
      correction,
      reports,
      insightIds: [...new Set(reports.flatMap((r) => r.insightIds))],
      changes,
      elapsedMs: reports.reduce((sum, r) => sum + r.elapsedMs, 0),
      startedAt: reports[0]?.startedAt ?? null,
      items: actions.length,
      partners: new Set(actions.map((a) => a.tenantId)).size,
      languages: new Set(actions.map((a) => a.locale)).size,
    };
  });
}
