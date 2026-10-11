/**
 * Approvals: the items a partner's policy holds for an editor, and what editors decided. Read
 * from the match's own feed: a decision is the item's next version on it, so the latest version of
 * each partner's item says where it stands.
 */
import type { TenantItemEntry } from "@/contracts/feed";

import type { BroadcastState } from "./broadcast";

const ENGLISH = "en-GB";

function versionKey(item: TenantItemEntry): string {
  return `${item.tenantId}/${item.overlay.itemId}`;
}

/** Each partner's item once, as its latest version, in the order the items first appeared. */
export function latestVersions(state: BroadcastState): TenantItemEntry[] {
  const latest = new Map<string, TenantItemEntry>();
  for (const item of state.items) latest.set(versionKey(item), item);
  return [...latest.values()];
}

/** Items waiting for an editor, oldest first: the order they should be decided in. */
export function waiting(state: BroadcastState): TenantItemEntry[] {
  return latestVersions(state).filter((item) => item.state === "pending_approval");
}

/** What editors decided, newest first. */
export function decisions(state: BroadcastState): TenantItemEntry[] {
  return latestVersions(state)
    .filter((item) => item.approval !== null)
    .sort((a, b) => b.entrySeq - a.entrySeq);
}

/** The English partner's version of the same insight, to read a held item against; nothing for
 * an item already in English or one no English partner received. */
export function englishVersion(
  state: BroadcastState,
  item: TenantItemEntry,
): TenantItemEntry | null {
  const insightId = item.localized?.insightId;
  if (item.overlay.locale === ENGLISH || insightId === undefined) return null;
  return (
    latestVersions(state).find(
      (other) => other.overlay.locale === ENGLISH && other.localized?.insightId === insightId,
    ) ?? null
  );
}

/** Whether a correction targets an event the item's claims rest on: such an item cannot air. */
export function correctedSince(state: BroadcastState, item: TenantItemEntry): boolean {
  const evidence = new Set(item.localized?.claims.flatMap((c) => c.evidence.eventIds) ?? []);
  return state.corrections.some((c) => evidence.has(c.correction.targetEventId));
}
