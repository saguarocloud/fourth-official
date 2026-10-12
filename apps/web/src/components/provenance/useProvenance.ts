"use client";

import { useEffect, useState } from "react";

import { parseAnswer, type ProvenanceAnswer } from "@/domain/provenance";

/** Where reading an item's record stands. */
export type Lookup =
  | { readonly status: "idle" }
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly answer: ProvenanceAnswer }
  | { readonly status: "missing" }
  | { readonly status: "busy" }
  | { readonly status: "unavailable" };

const IDLE: Lookup = { status: "idle" };
const LOADING: Lookup = { status: "loading" };
const FAILED: Readonly<Record<number, Lookup>> = {
  404: { status: "missing" },
  429: { status: "busy" },
};

async function lookUp(itemId: string, signal: AbortSignal): Promise<Lookup> {
  const response = await fetch(`/api/items/${encodeURIComponent(itemId)}/provenance`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) return FAILED[response.status] ?? { status: "unavailable" };
  const answer = parseAnswer(await response.json());
  // A record of any other item than the one asked for is no answer for this one.
  const ofAnother = answer?.provenance && answer.provenance.record.itemId !== itemId;
  return answer && !ofAnother ? { status: "ready", answer } : { status: "unavailable" };
}

interface Settled {
  readonly key: string;
  readonly lookup: Lookup;
}

/** An item's signed record and its check, read once per item and again on retry. */
export function useProvenance(itemId: string | null): {
  readonly lookup: Lookup;
  readonly retry: () => void;
} {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled | null>(null);
  const key = `${attempt}:${itemId}`;

  useEffect(() => {
    if (itemId === null) return;
    const controller = new AbortController();
    lookUp(itemId, controller.signal)
      .catch((): Lookup => ({ status: "unavailable" }))
      .then((lookup) => {
        if (!controller.signal.aborted) setSettled({ key, lookup });
      });
    return () => controller.abort();
  }, [itemId, key]);

  const lookup = itemId === null ? IDLE : settled?.key === key ? settled.lookup : LOADING;
  return { lookup, retry: () => setAttempt((n) => n + 1) };
}
