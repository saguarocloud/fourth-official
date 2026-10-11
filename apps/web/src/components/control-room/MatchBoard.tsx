import { LedReadout } from "@/components/led/LedReadout";
import { TallyLight } from "@/components/ui/TallyLight";
import { clubByCode, type Match, type Partner } from "@/domain/matchday";
import { footballMinute, formatLatency, formatMatchClock, formatMatchMinute } from "@/lib/format";

interface MatchBoardProps {
  readonly match: Match;
  readonly partners: readonly Partner[];
  readonly sloMs: number;
  readonly locale?: string;
}

/** One match as the studio sees it: the scoreboard, who is on air, and how publishing is going. */
export function MatchBoard({ match, partners, sloMs, locale = "en-GB" }: MatchBoardProps) {
  const home = clubByCode(match.home);
  const away = clubByCode(match.away);
  const minute = formatMatchMinute(footballMinute(match.minute), match.period);
  const withinSlo = match.p95LatencyMs <= sloMs;
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
        <LedReadout
          text={formatMatchClock(match.minute, match.second)}
          label={`Match clock ${formatMatchClock(match.minute, match.second)}`}
          dotSize={3}
        />
        <span className="match-board__minute">{minute}</span>
      </div>

      <ul className="match-board__tally" aria-label="Partners on air">
        {partners.map((partner) => (
          <li key={partner.id}>
            <TallyLight live={match.onAir[partner.id]} partner={partner.name} />
            <span className="match-board__partner" aria-hidden="true">
              {partner.name}
            </span>
          </li>
        ))}
      </ul>

      <ul className="match-board__stats" aria-label="Publishing activity">
        <li>
          <span className="stat__value">{match.itemsPerMinute.toLocaleString(locale)}</span>
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
          <span className="stat__value">{formatLatency(match.p95LatencyMs, locale)}</span>
          <span className="stat__label">{withinSlo ? "p95, within SLO" : "p95, outside SLO"}</span>
        </li>
      </ul>
    </article>
  );
}
