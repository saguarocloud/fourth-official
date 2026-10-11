/**
 * Display formatting for match and operations data. Every function is pure, locale-aware and
 * rejects values that cannot be real, so a bad upstream number fails loudly instead of rendering.
 */

const SECONDS_PER_MINUTE = 60;
const MILLISECONDS_PER_SECOND = 1000;
const CENTS_PER_UNIT = 100;
const REGULATION_END: Record<1 | 2, number> = { 1: 45, 2: 90 };
const PERIOD_START: Record<1 | 2, number> = { 1: 1, 2: 46 };
// Joins a number to its unit so the pair never wraps across lines (Intl does the same).
const NBSP = "\u00a0";

function requireNonNegativeInteger(value: number, name: string): void {
  if (!Number.isInteger(value) || value < 0) {
    throw new RangeError(`${name} must be a non-negative integer, got ${value}`);
  }
}

const pad2 = (value: number): string => value.toString().padStart(2, "0");

/** Running match clock as `mm:ss`, e.g. `67:12`. */
export function formatMatchClock(minute: number, second: number): string {
  requireNonNegativeInteger(minute, "minute");
  requireNonNegativeInteger(second, "second");
  if (second >= SECONDS_PER_MINUTE) {
    throw new RangeError(`second must be below ${SECONDS_PER_MINUTE}, got ${second}`);
  }
  return `${pad2(minute)}:${pad2(second)}`;
}

/** Broadcast minute notation: `61'`, or `90+3'` in added time. */
export function formatMatchMinute(minute: number, period: 1 | 2): string {
  requireNonNegativeInteger(minute, "minute");
  if (minute < PERIOD_START[period]) {
    throw new RangeError(`minute ${minute} cannot fall in period ${period}`);
  }
  const regulationEnd = REGULATION_END[period];
  return minute > regulationEnd ? `${regulationEnd}+${minute - regulationEnd}'` : `${minute}'`;
}

/** Latency: milliseconds below one second, otherwise seconds with one decimal. */
export function formatLatency(milliseconds: number, locale: string): string {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) {
    throw new RangeError(`latency must be a non-negative number, got ${milliseconds}`);
  }
  if (milliseconds < MILLISECONDS_PER_SECOND) {
    return `${Math.round(milliseconds).toLocaleString(locale)}${NBSP}ms`;
  }
  const seconds = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(milliseconds / MILLISECONDS_PER_SECOND);
  return `${seconds}${NBSP}s`;
}

/** Cost from integer cents, shown to the cent in US dollars. */
export function formatCost(cents: number, locale: string): string {
  requireNonNegativeInteger(cents, "cents");
  return new Intl.NumberFormat(locale, { style: "currency", currency: "USD" }).format(
    cents / CENTS_PER_UNIT,
  );
}

/** A ratio between 0 and 1 as a whole percentage in the viewer's locale. */
export function formatPercent(ratio: number, locale: string): string {
  if (!Number.isFinite(ratio) || ratio < 0 || ratio > 1) {
    throw new RangeError(`ratio must be between 0 and 1, got ${ratio}`);
  }
  return new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(
    ratio,
  );
}
