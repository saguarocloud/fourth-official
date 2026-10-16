"use client";

import { useEffect, useState } from "react";

import type { OperationsReport } from "@/contracts/operations";
import { parseOperations } from "@/domain/operations";

/** How often the report is read again: a running match changes it by the second. */
export const POLL_MS = 5000;

export type Lookup =
  | { readonly status: "loading" }
  | {
      readonly status: "ready";
      readonly report: OperationsReport;
      /** The last read failed: this is the report as it stood before. */
      readonly stale: boolean;
    }
  | { readonly status: "unavailable" };

async function read(signal: AbortSignal): Promise<OperationsReport> {
  const response = await fetch("/api/operations", { cache: "no-store", signal });
  if (!response.ok) throw new Error(`operations answered ${response.status}`);
  const report = parseOperations(await response.json());
  if (report === null) throw new Error("operations answered something other than a report");
  return report;
}

/** A reading that has not settled by then is given up, so a stalled connection never stops the
 * page from reading again. */
export const READ_TIMEOUT_MS = POLL_MS * 2;

/** The matchday run as the API measured it, read on arrival and every few seconds after. A
 * failed or stalled read keeps the last report on show, marked stale. A read in flight is never
 * overtaken by the next; the page reads nothing while it is hidden, and reads at once when it is
 * shown again. */
export function useOperations(): Lookup {
  const [lookup, setLookup] = useState<Lookup>({ status: "loading" });

  useEffect(() => {
    let unmounted = false;
    let inFlight: AbortController | null = null;
    async function load() {
      if (inFlight !== null || document.hidden) return;
      const controller = new AbortController();
      inFlight = controller;
      const timeout = setTimeout(() => controller.abort(), READ_TIMEOUT_MS);
      try {
        const report = await read(controller.signal);
        if (!unmounted) setLookup({ status: "ready", report, stale: false });
      } catch {
        if (unmounted) return;
        setLookup((last) =>
          last.status === "ready" ? { ...last, stale: true } : { status: "unavailable" },
        );
      } finally {
        clearTimeout(timeout);
        inFlight = null;
      }
    }
    const onShow = () => void load();
    void load();
    const timer = setInterval(() => void load(), POLL_MS);
    document.addEventListener("visibilitychange", onShow);
    return () => {
      unmounted = true;
      inFlight?.abort();
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onShow);
    };
  }, []);

  return lookup;
}
