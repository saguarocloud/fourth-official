"use client";

import { ActivityFeed } from "@/components/control-room/ActivityFeed";
import { MatchBoard } from "@/components/control-room/MatchBoard";
import { SubstitutionBoard } from "@/components/control-room/SubstitutionBoard";
import { useOperations } from "@/components/operations/useOperations";
import { AppShell } from "@/components/shell/AppShell";
import { PARTNERS } from "@/domain/broadcast";
import { controlRoom, parseWall } from "@/domain/controlRoom";
import { matchdayVerdict, type Verdict } from "@/domain/matchday";
import { usePolled } from "@/lib/usePolled";

const STUDIO = "Meridian League Studios";
const READING: Verdict = { tone: "neutral", text: "Reading the matchday." };
const UNANSWERED: Verdict = {
  tone: "neutral",
  text: "The matchday service did not answer. This page reads it again every few seconds.",
};

/** The Control Room: every match of the matchday on one wall, what is on air and what awaits a
 * person, read live from the API's wall and what operations measured. */
export function ControlRoomScreen() {
  const wall = usePolled("/api/wall", parseWall);
  const operations = useOperations();
  const room =
    wall.status === "ready"
      ? controlRoom(wall.report, operations.status === "ready" ? operations.report : null)
      : null;
  const stale = wall.status === "ready" && wall.stale;
  let verdict = READING;
  if (wall.status === "unavailable") verdict = UNANSWERED;
  // A frozen wall claims nothing: its lamp goes out until a reading succeeds again.
  else if (room)
    verdict = { ...matchdayVerdict(room.summary), ...(stale ? { tone: "neutral" } : {}) };
  const sloMs = room?.summary.sloMs ?? null;

  return (
    <AppShell
      current="/"
      summary={room?.summary}
      studio={STUDIO}
      replay
      rail={
        room && (
          <>
            {room.latestCorrection && (
              <section aria-labelledby="latest-correction">
                <h2 id="latest-correction" className="panel-heading">
                  Latest correction
                </h2>
                <SubstitutionBoard correction={room.latestCorrection} />
              </section>
            )}
            <section aria-labelledby="activity">
              <h2 id="activity" className="panel-heading">
                Activity
              </h2>
              <ActivityFeed entries={room.activity} partners={PARTNERS} />
            </section>
          </>
        )
      }
    >
      <header className="page-header">
        <h1>Control Room</h1>
        {room && (
          <p>{`Matchday · ${room.summary.liveMatches} of ${room.matches.length} matches live · ${PARTNERS.length} partners`}</p>
        )}
        <p role="status" aria-label="Matchday verdict" className="verdict" data-tone={verdict.tone}>
          <span aria-hidden="true" className="verdict__lamp" />
          {verdict.text}
        </p>
        {wall.status === "ready" && wall.stale && (
          <p className="statement__stale">
            The last reading failed: this is the matchday as read at{" "}
            {wall.report.generatedAt.slice(11, 19)} UTC.
          </p>
        )}
      </header>
      {room && (
        <section aria-label="Match wall" className="match-wall">
          {room.matches.map((match) => (
            <MatchBoard key={match.id} match={match} partners={PARTNERS} sloMs={sloMs} />
          ))}
        </section>
      )}
      <p className="page-footnote">
        All data is synthetic. The league, clubs, players and partners are fictional.
      </p>
    </AppShell>
  );
}
