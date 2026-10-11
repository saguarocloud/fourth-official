"use client";

import { useSearchParams } from "next/navigation";

import { MatchSwitcher } from "@/components/match-live/MatchSwitcher";
import type { Folding } from "@/components/matchday/useFeedStream";
import { useFeedStream } from "@/components/matchday/useFeedStream";
import { useMatches, useRunKey } from "@/components/matchday/useMatchday";
import { useTenants } from "@/components/matchday/useTenants";
import { AppShell } from "@/components/shell/AppShell";
import { applyBroadcast, type BroadcastState, emptyBroadcast } from "@/domain/broadcast";
import { FEATURED_MATCH, isMatchId } from "@/lib/matchId";

import { ApprovalsFloor } from "./ApprovalsFloor";
import type { Phase } from "./verdict";

export { SETTLE_MS } from "./ApprovalsFloor";

const BROADCAST: Folding<BroadcastState> = { empty: emptyBroadcast, apply: applyBroadcast };

/** The Approvals screen: which match, and its feed. The floor below is keyed by match, so
 * switching matches starts every piece of the desk afresh. */
export function Approvals() {
  const params = useSearchParams();
  const { matches, failed } = useMatches({ availability: false });
  const tenants = useTenants();
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED_MATCH;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED_MATCH);
  const matchId = current?.matchId ?? asked;
  const runKey = useRunKey(matchId, current?.state ?? null);
  const { view, connection, generation } = useFeedStream(matchId, runKey, BROADCAST);
  const phase: Phase = failed
    ? "unavailable"
    : matches === null
      ? "loading"
      : connection === "ended" && current?.state === "running"
        ? "finished"
        : (current?.state ?? "idle");

  return (
    <AppShell current="/approvals" studio="Meridian League Studios" replay>
      <ApprovalsFloor
        key={matchId}
        matchId={matchId}
        title={current ? `${current.homeName} v ${current.awayName} · Meridian League` : null}
        switcher={
          matches && <MatchSwitcher matches={matches} current={matchId} path="/approvals" />
        }
        view={view}
        generation={generation}
        phase={phase}
        tenants={tenants}
      />
      <p className="page-footnote">
        All data is synthetic. Decisions are recorded against each partner&apos;s duty editor, a
        named demo identity: this demo has no sign-in. Approved items air from the match clock.
      </p>
    </AppShell>
  );
}
