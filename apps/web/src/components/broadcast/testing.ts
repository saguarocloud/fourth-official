/** Test doubles for Broadcast Preview: the recorded m42 feed with every partner's items. */
import type { ClockEntry, FeedEntry, TenantItemEntry } from "@/contracts/feed";
import type { PartnerId } from "@/domain/broadcast";
import feedM42 from "@/fixtures/feed-m42-partners.json";

export const FEED = feedM42 as unknown as FeedEntry[];

/** The feed as it stood before the corrections desk acted: the window in which a held item may
 * rest on a fact a correction has already changed. */
export const BEFORE_DESK = FEED.filter(
  (e) =>
    e.kind !== "correction_report" &&
    !(
      e.kind === "tenant_item" &&
      (e.state === "retracted" || e.state === "amended" || e.overlay.supersedes !== null)
    ),
);

export function itemOf(partner: PartnerId, template: string, nth = 0): TenantItemEntry {
  const items = FEED.filter(
    (e): e is TenantItemEntry =>
      e.kind === "tenant_item" && e.tenantId === partner && e.overlay.content.template === template,
  );
  const item = items[nth];
  if (item === undefined) throw new Error(`no ${template} for ${partner}`);
  return item;
}

/** A clock entry after the whole feed, standing at the moment a graphic comes in. */
export function clockAt(item: TenantItemEntry): ClockEntry {
  const last = FEED.filter((e): e is ClockEntry => e.kind === "clock").at(-1)!;
  const seq = Math.max(...FEED.map((e) => e.entrySeq)) + 1;
  return { ...last, entrySeq: seq, clock: item.overlay.inAt };
}
