"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo } from "react";

import type { TenantItemEntry } from "@/contracts/feed";
import { MatchSwitcher } from "@/components/match-live/MatchSwitcher";
import type { Folding } from "@/components/matchday/useFeedStream";
import { useFeedStream } from "@/components/matchday/useFeedStream";
import { useMatches, useRunKey } from "@/components/matchday/useMatchday";
import { AppShell } from "@/components/shell/AppShell";
import { PHASE_STATES } from "@/components/ui/phaseState";
import { StatusLamp } from "@/components/ui/StatusLamp";
import {
  applyBroadcast,
  type BroadcastState,
  emptyBroadcast,
  instant,
  PARTNERS,
  phaseAt,
} from "@/domain/broadcast";
import { itemsOnRecord } from "@/domain/provenance";
import { formatMatchMinute, footballMinute } from "@/lib/format";
import { FEATURED_MATCH, isMatchId } from "@/lib/matchId";

import { ProvenanceRecord } from "./ProvenanceRecord";
import { type Lookup, useProvenance } from "./useProvenance";
import { provenanceVerdict } from "./verdict";

const BROADCAST: Folding<BroadcastState> = { empty: emptyBroadcast, apply: applyBroadcast };

function codeOf(tenantId: string): string {
  return PARTNERS.find((p) => p.id === tenantId)?.code ?? tenantId;
}

function minuteOf(item: TenantItemEntry): string {
  const { minute, period } = item.overlay.inAt;
  return formatMatchMinute(footballMinute(minute), period === 2 ? 2 : 1);
}

interface PickerProps {
  readonly matchId: string;
  readonly items: readonly TenantItemEntry[];
  readonly view: BroadcastState;
  readonly current: string | null;
}

function Picker({ matchId, items, view, current }: PickerProps) {
  const now = view.clock ? instant(view.clock.clock) : null;
  return (
    <nav aria-label="Items on record" className="picker">
      <ul>
        {items.map((item) => (
          <li key={item.overlay.itemId}>
            <Link
              href={`/provenance?match=${matchId}&item=${item.overlay.itemId}`}
              className="picker__item"
              aria-current={item.overlay.itemId === current ? "page" : undefined}
              scroll={false}
            >
              <span className="picker__code">{codeOf(item.tenantId)}</span>
              <span lang={item.overlay.locale} className="picker__headline">
                {item.rendered?.headline ?? item.localized?.headline}
              </span>
              <span className="picker__meta">
                <time className="picker__minute">{minuteOf(item)}</time>
                <StatusLamp state={PHASE_STATES[phaseAt(item, now)]} compact />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

const NOTES: Partial<Record<Lookup["status"], string>> = {
  loading: "Reading the signed record.",
  missing:
    "No record has been issued for this item yet. The studio signs each item as it is published; this one may still be on its way.",
  busy: "Too many reads from here. Wait a moment and try again.",
  unavailable: "The record could not be read: the match service did not answer.",
};

interface RecordPaneProps {
  readonly itemId: string;
  readonly lookup: Lookup;
  readonly retry: () => void;
}

function RecordPane({ itemId, lookup, retry }: RecordPaneProps) {
  return (
    <section aria-label="Signed record" className="provenance__record">
      {lookup.status === "ready" ? (
        <>
          <ProvenanceRecord answer={lookup.answer} />
          <p className="provenance__public">
            <Link href={`/verify/${itemId}`} className="provenance__public-link">
              Open the public verification page
              <ArrowUpRight aria-hidden="true" strokeWidth={1.75} />
            </Link>
          </p>
        </>
      ) : (
        <div className="provenance__note" data-status={lookup.status}>
          <p>{NOTES[lookup.status]}</p>
          {(lookup.status === "busy" || lookup.status === "unavailable") && (
            <button type="button" className="key" data-size="sm" onClick={retry}>
              <span>Try again</span>
            </button>
          )}
        </div>
      )}
    </section>
  );
}

/** Provenance: every partner item this match, and the signed record of the one chosen. */
export function ProvenanceScreen() {
  const params = useSearchParams();
  const { matches, failed } = useMatches({ availability: false });
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED_MATCH;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED_MATCH);
  const matchId = current?.matchId ?? asked;
  const runKey = useRunKey(matchId, current?.state ?? null);
  const { view } = useFeedStream(matchId, runKey, BROADCAST);
  const items = useMemo(() => itemsOnRecord(view), [view]);
  const wanted = params.get("item");
  const chosen =
    items.find((i) => i.overlay.itemId === wanted)?.overlay.itemId ??
    items[0]?.overlay.itemId ??
    null;
  const { lookup, retry } = useProvenance(chosen);
  const verdict = provenanceVerdict(lookup, items.length, failed, matches === null);

  return (
    <AppShell current="/provenance" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Provenance</h1>
        {current && <p>{`${current.homeName} v ${current.awayName} · Meridian League`}</p>}
        <p
          role="status"
          aria-label="Provenance verdict"
          className="verdict"
          data-tone={verdict.tone}
        >
          <span aria-hidden="true" className="verdict__lamp" />
          {verdict.text}
        </p>
      </header>
      <div className="provenance__controls">
        {matches && <MatchSwitcher matches={matches} current={matchId} path="/provenance" />}
      </div>
      {items.length > 0 && chosen !== null && (
        <div className="provenance">
          <Picker matchId={matchId} items={items} view={view} current={chosen} />
          <RecordPane itemId={chosen} lookup={lookup} retry={retry} />
        </div>
      )}
      <p className="page-footnote">
        All data is synthetic. The studio signs a record of every partner item as it is published:
        who wrote it, what it rests on, how it was checked and what became of it.
      </p>
    </AppShell>
  );
}
