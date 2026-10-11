/**
 * A fixed-window limit per client, in memory on each web replica: a bound on abuse of the
 * demo's routes, not an exact quota. Memory is bounded too: past `maxClients`, a newcomer waits
 * for the next sweep rather than growing the table, and the table is swept once a window, not on
 * every request.
 */

export interface RateLimit {
  /** Take one from the client's share: 0 if allowed, else the seconds until it may try again. */
  take(client: string): number;
  /** Clients currently tracked. */
  size(): number;
}

interface Options {
  readonly perWindow: number;
  readonly windowMs: number;
  readonly maxClients?: number;
  readonly now?: () => number;
}

const MAX_CLIENTS = 10_000;

export function rateLimit({
  perWindow,
  windowMs,
  maxClients = MAX_CLIENTS,
  now = Date.now,
}: Options): RateLimit {
  const windows = new Map<string, { start: number; used: number }>();
  let nextSweep = now() + windowMs;
  const seconds = (ms: number) => Math.max(1, Math.ceil(ms / 1000));

  function sweep(at: number): void {
    if (at < nextSweep) return;
    for (const [key, window] of windows) {
      if (at - window.start >= windowMs) windows.delete(key);
    }
    nextSweep = at + windowMs;
  }

  return {
    take(client) {
      const at = now();
      sweep(at);
      const current = windows.get(client);
      const live = current !== undefined && at - current.start < windowMs ? current : undefined;
      if (live === undefined && current === undefined && windows.size >= maxClients) {
        return seconds(nextSweep - at);
      }
      const window = live ?? { start: at, used: 0 };
      if (window.used >= perWindow) return seconds(window.start + windowMs - at);
      windows.set(client, { ...window, used: window.used + 1 });
      return 0;
    },
    size: () => windows.size,
  };
}
