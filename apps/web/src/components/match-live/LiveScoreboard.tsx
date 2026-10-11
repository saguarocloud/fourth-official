import { LedReadout } from "@/components/led/LedReadout";
import type { ClockEntry } from "@/contracts/feed";
import type { RunState } from "@/domain/live";
import { formatMatchClock, formatMatchMinute } from "@/lib/format";

export interface MatchNames {
  readonly home: string;
  readonly away: string;
  readonly homeName: string;
  readonly awayName: string;
}

interface LiveScoreboardProps {
  readonly names: MatchNames;
  readonly clock: ClockEntry | null;
  readonly state: RunState;
}

const STATE_LABEL: Record<RunState, string> = {
  idle: "Not started",
  running: "Live",
  finished: "Full time",
  failed: "Stopped",
};

/** The match as the fourth official's board shows it: score, clock, and where play stands. */
export function LiveScoreboard({ names, clock, state }: LiveScoreboardProps) {
  const home = clock?.score.home ?? 0;
  const away = clock?.score.away ?? 0;
  const time = clock ? formatMatchClock(clock.clock.minute, clock.clock.second) : "00:00";
  const minute = clock ? formatMatchMinute(clock.clock.minute, clock.clock.period) : "";
  const heading = `${names.homeName} ${home}, ${names.awayName} ${away}${minute ? `, ${minute}` : ""}`;

  return (
    <section className="live-board" aria-labelledby="live-board-heading" data-state={state}>
      <h2 id="live-board-heading" className="sr-only">
        {heading}
      </h2>
      <div className="live-board__scoreline" aria-hidden="true">
        <LedReadout text={`${names.home} ${home}-${away} ${names.away}`} dotSize={6} />
      </div>
      <div className="live-board__names" aria-hidden="true">
        <span>{names.homeName}</span>
        <span>{names.awayName}</span>
      </div>
      <div className="live-board__clock">
        <LedReadout text={time} label={`Match clock ${time}`} dotSize={3} />
        <span className="live-board__minute tabular">{minute}</span>
        <span className="live-board__state" data-state={state}>
          <span aria-hidden="true" className="live-board__lamp" />
          {STATE_LABEL[state]}
        </span>
      </div>
    </section>
  );
}
