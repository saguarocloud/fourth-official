import Link from "next/link";

import type { MatchSummary } from "./types";

interface MatchSwitcherProps {
  readonly matches: readonly MatchSummary[];
  readonly current: string;
}

/** The matchday's matches, one key each; the current one is lit. */
export function MatchSwitcher({ matches, current }: MatchSwitcherProps) {
  return (
    <nav aria-label="Matches" className="match-switcher">
      <ul>
        {matches.map((match) => (
          <li key={match.matchId}>
            <Link
              href={`/match?match=${match.matchId}`}
              className="match-switcher__key"
              aria-current={match.matchId === current ? "page" : undefined}
              scroll={false}
            >
              <span className="match-switcher__codes">{`${match.home} v ${match.away}`}</span>
              <span className="sr-only">{`${match.homeName} v ${match.awayName}`}</span>
              <span className="match-switcher__state" data-state={match.state}>
                {match.state === "running" ? "Live" : match.state === "finished" ? "FT" : ""}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
