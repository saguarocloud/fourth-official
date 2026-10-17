"use client";

import { useEffect, useState } from "react";

/** How often a live report is read again: a running match changes it by the second. */
export const POLL_MS = 5000;

/** A reading that has not settled by then is given up, so a stalled connection never stops the
 * page from reading again. */
export const READ_TIMEOUT_MS = POLL_MS * 2;

export type Polled<T> =
  | { readonly status: "loading" }
  | {
      readonly status: "ready";
      readonly report: T;
      /** The last read failed: this is the report as it stood before. */
      readonly stale: boolean;
    }
  | { readonly status: "unavailable" };

async function read<T>(
  path: string,
  parse: (raw: unknown) => T | null,
  signal: AbortSignal,
): Promise<T> {
  const response = await fetch(path, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`${path} answered ${response.status}`);
  const report = parse(await response.json());
  if (report === null) throw new Error(`${path} answered something it should not`);
  return report;
}

/** A live report from one of the web app's own routes, read on arrival and every few seconds
 * after. A failed or stalled read keeps the last report on show, marked stale. A read in flight
 * is never overtaken by the next; the page reads nothing while it is hidden, and reads at once
 * when it is shown again. `parse` must be stable (a module-level function). */
export function usePolled<T>(path: string, parse: (raw: unknown) => T | null): Polled<T> {
  const [lookup, setLookup] = useState<Polled<T>>({ status: "loading" });

  useEffect(() => {
    let unmounted = false;
    let inFlight: AbortController | null = null;
    async function load() {
      if (inFlight !== null || document.hidden) return;
      const controller = new AbortController();
      inFlight = controller;
      const timeout = setTimeout(() => controller.abort(), READ_TIMEOUT_MS);
      try {
        const report = await read(path, parse, controller.signal);
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
  }, [path, parse]);

  return lookup;
}
