/** Test doubles for Match Live: the recorded m42 feed and a scriptable EventSource. */
import type { CorrectionEntry, FeedEntry, InsightEntry } from "@/contracts/feed";
import { foldFeed, type LiveItem } from "@/domain/live";
import feedM42 from "@/fixtures/feed-m42.json";

import type { MatchSummary } from "./types";

export const FEED = feedM42 as unknown as FeedEntry[];
export const LIVE = foldFeed(FEED);

export function itemAt(minute: number): LiveItem {
  const item = LIVE.items.find((i) => i.moment.clock.minute === minute);
  if (item === undefined) throw new Error(`no item at ${minute}`);
  return item;
}

export function correctionsOf(kind: CorrectionEntry["correction"]["kind"]): CorrectionEntry {
  const correction = LIVE.corrections.find((c) => c.correction.kind === kind);
  if (correction === undefined) throw new Error(`no ${kind} correction`);
  return correction;
}

/** The same insight, as if a model had written it after one refused draft. */
export function modelWritten(insight: InsightEntry): InsightEntry {
  return {
    ...insight,
    insight: {
      ...insight.insight,
      provenance: { ...insight.insight.provenance, producedBy: "model", model: "fast" },
    },
    attempts: [
      {
        ...insight.attempts[0]!,
        number: 1,
        model: "fast",
        outcome: "failed",
        findings: ["BARE_NUMBER"],
      },
      { ...insight.attempts[0]!, number: 2, model: "fast", outcome: "passed", findings: [] },
    ],
  } as InsightEntry;
}

export const MATCHES: MatchSummary[] = [
  {
    matchId: "m42",
    home: "HCY",
    away: "NGT",
    homeName: "Harbour City",
    awayName: "Northgate FC",
    state: "finished",
    entries: 110,
  },
  {
    matchId: "m43",
    home: "KBA",
    away: "ASV",
    homeName: "Kingsbridge Athletic",
    awayName: "Ashford Vale",
    state: "idle",
    entries: 0,
  },
];

type Listener = (event: MessageEvent<string>) => void;

function idOf(data: unknown): string {
  const seq = (data as { entrySeq?: unknown } | null)?.entrySeq;
  return typeof seq === "number" ? `1:${seq}` : "";
}

/** An EventSource the test drives: `emit` delivers a named event, `fail` an error. */
export class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static instances: FakeEventSource[] = [];

  readonly url: string;
  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private readonly listeners = new Map<string, Listener[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close(): void {
    this.readyState = FakeEventSource.CLOSED;
  }

  open(): void {
    this.readyState = FakeEventSource.OPEN;
    this.onopen?.();
  }

  /** Delivers `data` with the API's event id (`generation:entrySeq`), run 1 unless given. */
  emit(type: string, data: unknown, lastEventId = idOf(data)): void {
    const event = new MessageEvent<string>(type, { data: JSON.stringify(data), lastEventId });
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }

  fail(closed = false): void {
    if (closed) this.readyState = FakeEventSource.CLOSED;
    this.onerror?.();
  }
}
