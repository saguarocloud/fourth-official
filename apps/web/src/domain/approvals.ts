/**
 * Approvals: the items a partner's policy holds for an editor, and what editors decided. Read
 * from the match's own feed: a decision is the item's next version on it, so the latest version of
 * each partner's item says where it stands.
 */
import type { Approval, TenantItemEntry } from "@/contracts/feed";

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

/** An item an editor has decided on: it carries the decision. */
export type DecidedItem = TenantItemEntry & { readonly approval: Approval };

function isDecided(item: TenantItemEntry): item is DecidedItem {
  return item.approval !== null;
}

/** What editors decided, newest first. */
export function decisions(state: BroadcastState): DecidedItem[] {
  return latestVersions(state)
    .filter(isDecided)
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

/** Whether a correction rests on what the item's claims say, as the server decides it: the
 * claims' evidence and the moment's events, except that a void does not touch the VAR moment that
 * explains it, and a version the desk remade after a correction is not corrected by it. Such an
 * item cannot air. */
export function correctedSince(state: BroadcastState, item: TenantItemEntry): boolean {
  const localized = item.localized;
  if (localized === null) return false;
  const moment = state.moments[localized.momentId];
  const evidence = new Set([
    ...localized.claims.flatMap((c) => c.evidence.eventIds),
    ...(moment?.eventIds ?? []),
  ]);
  const remade = item.overlay.supersedes !== null;
  return state.corrections.some((c) => {
    const explainsTheVoid = moment?.kind === "var_overturn" && c.correction.kind === "EVENT_VOIDED";
    const madeAfter = remade && item.entrySeq > c.entrySeq;
    return !explainsTheVoid && !madeAfter && evidence.has(c.correction.targetEventId);
  });
}
