"use client";

import { useEffect, useState } from "react";

import { LedReadout } from "@/components/led/LedReadout";

const STUDIO_TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/** Wall-clock time at the studio in London, 24-hour. */
export function formatStudioTime(date: Date): string {
  return STUDIO_TIME.format(date);
}

const TICK_MS = 1000;
// Shown before the first tick: prerendered markup must never carry a stale time.
const UNSET = "--:--:--";

export function LiveClock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    // Re-arm on each wall-clock second so the display never skips or repeats a second.
    const tick = () => {
      const current = new Date();
      setNow(current);
      timer = setTimeout(tick, TICK_MS - (current.getTime() % TICK_MS));
    };
    tick();
    return () => clearTimeout(timer);
  }, []);

  if (!now) {
    return (
      <span className="live-clock" aria-hidden="true">
        <LedReadout text={UNSET} dotSize={3} />
      </span>
    );
  }
  const time = formatStudioTime(now);
  return (
    <span className="live-clock">
      <LedReadout text={time} label={`Studio time ${time}`} dotSize={3} />
    </span>
  );
}
