import { ActivityFeed } from "@/components/control-room/ActivityFeed";
import { MatchBoard } from "@/components/control-room/MatchBoard";
import { SubstitutionBoard } from "@/components/control-room/SubstitutionBoard";
import { AppShell } from "@/components/shell/AppShell";
import { matchdayVerdict, summarise } from "@/domain/matchday";
import { DEMO_MATCHDAY } from "@/fixtures/matchday";

export default function Home() {
  const matchday = DEMO_MATCHDAY;
  const summary = summarise(matchday.matches, {
    sloMs: matchday.sloMs,
    costCents: matchday.costCents,
  });
  const verdict = matchdayVerdict(summary);
  const featuredFirst = [...matchday.matches].sort(
    (a, b) => Number(b.featured) - Number(a.featured),
  );

  return (
    <AppShell
      current="/"
      summary={summary}
      studio={matchday.studio}
      replay
      rail={
        <>
          {matchday.latestCorrection && (
            <section aria-labelledby="latest-correction">
              <h2 id="latest-correction" className="panel-heading">
                Latest correction
              </h2>
              <SubstitutionBoard correction={matchday.latestCorrection} />
            </section>
          )}
          <section aria-labelledby="activity">
            <h2 id="activity" className="panel-heading">
              Activity
            </h2>
            <ActivityFeed entries={matchday.activity} partners={matchday.partners} />
          </section>
        </>
      }
    >
      <header className="page-header">
        <h1>Control Room</h1>
        <p>{`${matchday.label} · ${summary.liveMatches} matches live · ${matchday.partners.length} partners`}</p>
        <p role="status" aria-label="Matchday verdict" className="verdict" data-tone={verdict.tone}>
          <span aria-hidden="true" className="verdict__lamp" />
          {verdict.text}
        </p>
      </header>
      <section aria-label="Match wall" className="match-wall">
        {featuredFirst.map((match) => (
          <MatchBoard
            key={match.id}
            match={match}
            partners={matchday.partners}
            sloMs={matchday.sloMs}
          />
        ))}
      </section>
      <p className="page-footnote">
        All data is synthetic. The league, clubs, players and partners are fictional.
      </p>
    </AppShell>
  );
}
