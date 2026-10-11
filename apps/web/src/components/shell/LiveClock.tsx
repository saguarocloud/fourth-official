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
    const tick = () => setNow(new Date());
    tick();
    const timer = setInterval(tick, TICK_MS);
    return () => clearInterval(timer);
  }, []);

  const time = now ? formatStudioTime(now) : UNSET;
  return (
    <span className="live-clock">
      <LedReadout
        text={time}
        label={now ? `Studio time ${time}` : "Studio time loading"}
        tone="green"
        dotSize={2}
      />
    </span>
  );
}
