"use client";

import { useEffect, useState } from "react";

import { parseProvingGround, type ProvingGround } from "@/domain/proving";

/** Where reading the Proving Ground's recorded runs stands. */
export type Lookup =
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly ground: ProvingGround }
  | { readonly status: "busy" }
  | { readonly status: "unavailable" };

const LOADING: Lookup = { status: "loading" };
const TOO_MANY = 429;

async function lookUp(signal: AbortSignal): Promise<Lookup> {
  const response = await fetch("/api/proving-ground", { signal });
  if (response.status === TOO_MANY) return { status: "busy" };
  if (!response.ok) return { status: "unavailable" };
  const ground = parseProvingGround(await response.json());
  return ground ? { status: "ready", ground } : { status: "unavailable" };
}

interface Settled {
  readonly attempt: number;
  readonly lookup: Lookup;
}

/** The recorded runs and the gate's verdict, read once and again on retry. */
export function useProvingGround(): { readonly lookup: Lookup; readonly retry: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    lookUp(controller.signal)
      .catch((): Lookup => ({ status: "unavailable" }))
      .then((lookup) => {
        if (!controller.signal.aborted) setSettled({ attempt, lookup });
      });
    return () => controller.abort();
  }, [attempt]);

  const lookup = settled?.attempt === attempt ? settled.lookup : LOADING;
  return { lookup, retry: () => setAttempt((n) => n + 1) };
}
