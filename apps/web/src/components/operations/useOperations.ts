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

/** The matchday run as the API measured it, read on arrival and every few seconds after. A
 * failed read keeps the last report on show, marked stale. A read still in flight is never
 * overtaken by the next, and the page reads nothing while it is hidden. */
export function useOperations(): Lookup {
  const [lookup, setLookup] = useState<Lookup>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    let reading = false;
    async function load() {
      if (reading || document.hidden) return;
      reading = true;
      try {
        const report = await read(controller.signal);
        if (!controller.signal.aborted) setLookup({ status: "ready", report, stale: false });
      } catch {
        if (controller.signal.aborted) return;
        setLookup((last) =>
          last.status === "ready" ? { ...last, stale: true } : { status: "unavailable" },
        );
      } finally {
        reading = false;
      }
    }
    void load();
    const timer = setInterval(() => void load(), POLL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  return lookup;
}
