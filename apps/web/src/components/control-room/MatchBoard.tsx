import { LedReadout } from "@/components/led/LedReadout";
import { TallyLight } from "@/components/ui/TallyLight";
import type { Partner } from "@/domain/broadcast";
import { clubByCode, type Match } from "@/domain/matchday";
import { footballMinute, formatLatency, formatMatchClock, formatMatchMinute } from "@/lib/format";

interface MatchBoardProps {
  readonly match: Match;
  readonly partners: readonly Partner[];
  /** The on-air objective; none when it could not be read. */
  readonly sloMs: number | null;
  readonly locale?: string;
}

/** One match as the studio sees it: the scoreboard, who is on air, and how publishing is going. */
export function MatchBoard({ match, partners, sloMs, locale = "en-GB" }: MatchBoardProps) {
  const home = clubByCode(match.home);
  const away = clubByCode(match.away);
  const { clock } = match;
  const minute =
    clock === null ? "Not started" : formatMatchMinute(footballMinute(clock.minute), clock.period);
  const shown = clock === null ? "00:00" : formatMatchClock(clock.minute, clock.second);
  const p95 = match.p95LatencyMs;
  const withinSlo = p95 === null || sloMs === null || p95 <= sloMs;
  let latencyLabel = "p95, nothing aired yet";
  if (p95 !== null) latencyLabel = withinSlo ? "p95, within SLO" : "p95, outside SLO";
  const headingId = `match-${match.id}`;

  return (
    <article className="match-board" data-featured={match.featured} aria-labelledby={headingId}>
      <h2 id={headingId} className="sr-only">
        {`${home.name} ${match.homeScore}, ${away.name} ${match.awayScore}, ${minute}`}
      </h2>
      {/* One line, as on the physical board; it scales with the board, so the featured match reads largest. */}
      <div className="match-board__scoreline" aria-hidden="true">
        <LedReadout
          text={`${home.code} ${match.homeScore}-${match.awayScore} ${away.code}`}
          dotSize={6}
        />
      </div>
      <div className="match-board__names" aria-hidden="true">
        <span>{home.name}</span>
        <span>{away.name}</span>
      </div>
      <div className="match-board__clock">
        <LedReadout text={shown} label={`Match clock ${shown}`} dotSize={3} />
        <span className="match-board__minute">{minute}</span>
      </div>

      <ul className="match-board__tally" aria-label="Partners on air">
        {partners.map((partner) => (
          <li key={partner.id}>
            <TallyLight live={match.onAir.includes(partner.id)} partner={partner.name} />
            <span className="match-board__partner" aria-hidden="true">
              {partner.name}
            </span>
          </li>
        ))}
      </ul>

      <ul className="match-board__stats" aria-label="Publishing activity">
        <li>
          <span className="stat__value">
            {match.itemsPerMinute === null
              ? "–"
              : match.itemsPerMinute.toLocaleString(locale, { maximumFractionDigits: 1 })}
          </span>
          <span className="stat__label">Items per minute</span>
        </li>
        <li data-attention={match.pendingApprovals > 0 || undefined}>
          <span className="stat__value">{match.pendingApprovals}</span>
          <span className="stat__label">Pending approvals</span>
        </li>
        <li data-attention={match.corrections > 0 || undefined}>
          <span className="stat__value">{match.corrections}</span>
          <span className="stat__label">Corrections</span>
        </li>
        <li data-breach={!withinSlo || undefined}>
          <span className="stat__value">{p95 === null ? "–" : formatLatency(p95, locale)}</span>
          <span className="stat__label">{latencyLabel}</span>
        </li>
      </ul>
    </article>
  );
}
