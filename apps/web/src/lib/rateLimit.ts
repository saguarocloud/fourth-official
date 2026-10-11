/**
 * A fixed-window limit per client, in memory on each web replica: a bound on abuse of the
 * demo's write routes, not an exact quota.
 */

export interface RateLimit {
  /** Take one from the client's share: 0 if allowed, else the seconds until its window ends. */
  take(client: string): number;
  /** Clients currently tracked. */
  size(): number;
}

interface Options {
  readonly perWindow: number;
  readonly windowMs: number;
  readonly now?: () => number;
}

export function rateLimit({ perWindow, windowMs, now = Date.now }: Options): RateLimit {
  const windows = new Map<string, { start: number; used: number }>();
  return {
    take(client) {
      const at = now();
      for (const [key, window] of windows) {
        if (at - window.start >= windowMs) windows.delete(key);
      }
      const window = windows.get(client) ?? { start: at, used: 0 };
      if (window.used >= perWindow) return Math.ceil((window.start + windowMs - at) / 1000);
      windows.set(client, { ...window, used: window.used + 1 });
      return 0;
    },
    size: () => windows.size,
  };
}
