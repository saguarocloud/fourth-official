"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { MatchSwitcher } from "@/components/match-live/MatchSwitcher";
import type { Folding } from "@/components/matchday/useFeedStream";
import { useFeedStream } from "@/components/matchday/useFeedStream";
import { useMatches, useRunKey } from "@/components/matchday/useMatchday";
import { useTenants } from "@/components/matchday/useTenants";
import { AppShell } from "@/components/shell/AppShell";
import { correctedSince, decisions, waiting } from "@/domain/approvals";
import { applyBroadcast, type BroadcastState, emptyBroadcast, instant } from "@/domain/broadcast";
import { cleanReason } from "@/lib/decision";
import { isMatchId } from "@/lib/matchId";
import { sendDecision } from "@/lib/sendDecision";

import { DecisionLog } from "./DecisionLog";
import { Desk } from "./Desk";
import { ticketKey, Tickets } from "./Tickets";
import { approvalsVerdict } from "./verdict";

const FEATURED = "m42";
const BROADCAST: Folding<BroadcastState> = { empty: emptyBroadcast, apply: applyBroadcast };

interface Keys {
  readonly approve: () => void;
  readonly reject: () => void;
  readonly move: (by: number) => void;
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    target.closest("input, textarea, select, [contenteditable]") !== null
  );
}

export function Approvals() {
  const params = useSearchParams();
  const { matches, failed } = useMatches({ availability: false });
  const tenants = useTenants();
  const param = params.get("match");
  const asked = param !== null && isMatchId(param) ? param : FEATURED;
  const current =
    matches?.find((m) => m.matchId === asked) ?? matches?.find((m) => m.matchId === FEATURED);
  const matchId = current?.matchId ?? asked;
  const runKey = useRunKey(matchId, current?.state ?? null);
  const { view, connection, generation } = useFeedStream(matchId, runKey, BROADCAST);

  const queue = useMemo(() => waiting(view), [view]);
  const log = useMemo(() => decisions(view), [view]);
  const [chosen, setChosen] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  // The desk belongs to its match: switching matches starts from the oldest item again.
  const [shown, setShown] = useState(matchId);
  if (shown !== matchId) {
    setShown(matchId);
    setChosen(null);
    setRejecting(false);
  }

  const index = Math.max(
    0,
    queue.findIndex((i) => ticketKey(i) === chosen),
  );
  const item = queue[index] ?? null;
  const closed = current?.state !== "running" || connection === "ended";

  async function decide(decision: "approved" | "rejected", reason?: string) {
    if (item === null || generation === null || busy) return;
    setBusy(true);
    setMessage("");
    const outcome = await sendDecision(
      { tenantId: item.tenantId, matchId, itemId: item.overlay.itemId },
      reason === undefined ? { decision, generation } : { decision, generation, reason },
    );
    setBusy(false);
    if (outcome.ok) {
      setRejecting(false);
      setMessage(
        decision === "approved"
          ? "Approved. It goes on air from the match clock."
          : "Rejected. It stays off air.",
      );
    } else {
      setMessage(outcome.message);
    }
  }

  function sendReject(text: string) {
    const reason = cleanReason(text);
    if (reason === null) {
      setReasonError("Give a reason of one line.");
      return;
    }
    setReasonError(null);
    void decide("rejected", reason);
  }

  function move(by: number) {
    const next = queue[Math.min(queue.length - 1, Math.max(0, index + by))];
    if (next) setChosen(ticketKey(next));
  }

  // The keys act on the screen as it is now: the handler reads the latest actions from a ref.
  const keys = useRef<Keys>({ approve: () => {}, reject: () => {}, move: () => {} });
  useEffect(() => {
    const open = !closed && !busy && item !== null && generation !== null;
    keys.current = {
      approve: () => {
        if (open && item && !correctedSince(view, item)) void decide("approved");
      },
      reject: () => {
        if (!open) return;
        setReasonError(null);
        setRejecting(true);
      },
      move,
    };
  });
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || isTyping(event.target)) return;
      const key = event.key.toLowerCase();
      const act: Record<string, () => void> = {
        a: () => keys.current.approve(),
        r: () => keys.current.reject(),
        j: () => keys.current.move(1),
        arrowdown: () => keys.current.move(1),
        k: () => keys.current.move(-1),
        arrowup: () => keys.current.move(-1),
      };
      const run = act[key];
      if (run === undefined) return;
      // The key is spent on the shortcut: R must not also type into the reason it opens.
      event.preventDefault();
      run();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const verdict = approvalsVerdict({
    failed,
    loading: matches === null,
    closed,
    waiting: queue,
    decided: log.length,
  });
  const now = view.clock ? instant(view.clock.clock) : null;

  return (
    <AppShell current="/approvals" studio="Meridian League Studios" replay>
      <header className="page-header">
        <h1>Approvals</h1>
        {current && <p>{`${current.homeName} v ${current.awayName} · Meridian League`}</p>}
        <p
          role="status"
          aria-label="Approvals verdict"
          className="verdict"
          data-tone={verdict.tone}
        >
          <span aria-hidden="true" className="verdict__lamp" />
          {verdict.text}
        </p>
      </header>
      <div className="approvals__controls">
        {matches && <MatchSwitcher matches={matches} current={matchId} path="/approvals" />}
        <div className="approvals__move">
          <button
            type="button"
            className="key"
            data-size="sm"

            aria-keyshortcuts="K"
            disabled={index === 0}
            onClick={() => move(-1)}
          >
            <span>
              <span className="key-cap" aria-hidden="true">
                K
              </span>
              Previous
            </span>
          </button>
          <button
            type="button"
            className="key"
            data-size="sm"

            aria-keyshortcuts="J"
            disabled={index >= queue.length - 1}
            onClick={() => move(1)}
          >
            <span>
              <span className="key-cap" aria-hidden="true">
                J
              </span>
              Next
            </span>
          </button>
        </div>
      </div>
      <p className="approvals__message" role="status" aria-live="polite">
        {message}
      </p>
      <div className="approvals__floor">
        <Tickets
          items={queue}
          moments={view.moments}
          current={item ? ticketKey(item) : null}
          onChoose={setChosen}
        />
        {item && (
          <Desk
            key={ticketKey(item)}
            item={item}
            view={view}
            tenant={tenants?.get(item.tenantId)}
            actions={{
              closed,
              busy,
              rejecting,
              reasonError,
              onApprove: () => void decide("approved"),
              onReject: () => {
                setReasonError(null);
                setRejecting(true);
              },
              onCancel: () => setRejecting(false),
              onSendReject: sendReject,
            }}
          />
        )}
      </div>
      <DecisionLog items={log} now={now} />
      <p className="page-footnote">
        All data is synthetic. Decisions are recorded against each partner&apos;s duty editor, a
        named demo identity: this demo has no sign-in. Approved items air from the match clock.
      </p>
    </AppShell>
  );
}
