"use client";

import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import type { TenantInfo } from "@/components/matchday/useTenants";
import type { TenantItemEntry } from "@/contracts/feed";
import { correctedSince, decisions, waiting } from "@/domain/approvals";
import { type BroadcastState, instant } from "@/domain/broadcast";
import { cleanReason } from "@/lib/decision";
import { sendDecision } from "@/lib/sendDecision";

import { DecisionLog } from "./DecisionLog";
import { Desk } from "./Desk";
import { ticketKey, Tickets } from "./Tickets";
import { approvalsVerdict, type Phase } from "./verdict";

/** After the desk shows a different item, its keys wait this long: no decision lands on an item
 * the editor has not seen. */
export const SETTLE_MS = 600;

interface Keys {
  readonly approve: () => void;
  readonly reject: () => void;
  readonly move: (by: number) => void;
}

const ACTIONS: Readonly<Record<string, keyof Keys | "next" | "previous">> = {
  a: "approve",
  r: "reject",
  j: "next",
  k: "previous",
};

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    target.closest("input, textarea, select, [contenteditable='true'], [contenteditable='']") !==
      null
  );
}

interface FloorProps {
  readonly matchId: string;
  readonly title: string | null;
  readonly switcher: ReactNode;
  readonly view: BroadcastState;
  readonly generation: number | null;
  readonly phase: Phase;
  readonly tenants: ReadonlyMap<string, TenantInfo> | null;
}

export function ApprovalsFloor(props: FloorProps) {
  const { matchId, title, switcher, view, generation, phase, tenants } = props;
  // Items decided here leave the queue at once, before the feed confirms them.
  const [sent, setSent] = useState<ReadonlySet<string>>(new Set());
  const queue = useMemo(
    () => waiting(view).filter((item) => !sent.has(ticketKey(item))),
    [view, sent],
  );
  const log = useMemo(() => decisions(view), [view]);
  const [chosen, setChosen] = useState<string | null>(null);
  const [rejectingFor, setRejectingFor] = useState<string | null>(null);
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [settled, setSettled] = useState(false);
  // What the desk showed last, and where: the place it keeps, and what left it.
  const [desk, setDesk] = useState<{ item: TenantItemEntry | null; index: number }>({
    item: null,
    index: 0,
  });
  const [decidedHere, setDecidedHere] = useState<string | null>(null);
  const inFlight = useRef(false);
  // Focus follows the editor's own actions only: set by a decision or a move, spent on use.
  const focusNext = useRef(false);

  // The desk keeps its place: when its item leaves the queue, the one that took its place shows.
  const picked = queue.findIndex((i) => ticketKey(i) === chosen);
  const index = picked >= 0 ? picked : Math.min(desk.index, Math.max(queue.length - 1, 0));
  const item = queue[index] ?? null;
  const key = item ? ticketKey(item) : null;
  const closed = phase !== "running";
  const deskKey = desk.item ? ticketKey(desk.item) : null;
  if (key !== deskKey || index !== desk.index) {
    // Adjusted during render (React's pattern for reacting to a changed value), not in an effect.
    setDesk({ item, index });
    if (key !== deskKey) {
      setSettled(false);
      setRejectingFor(null);
      setReasonError(null);
      if (desk.item) {
        const gone = !queue.some((i) => ticketKey(i) === deskKey);
        if (gone && decidedHere !== deskKey) {
          const next = key === null ? "Nothing else waits." : "The next item is on the desk.";
          setMessage(`"${desk.item.rendered?.headline ?? ""}" was decided elsewhere. ${next}`);
        }
      }
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => setSettled(true), SETTLE_MS);
    return () => clearTimeout(timer);
  }, [key]);

  // After the editor's own decision or move, focus goes to the item now on the desk, or to the
  // queue when nothing is left; an item arriving on its own never takes focus.
  useEffect(() => {
    if (!focusNext.current) return;
    focusNext.current = false;
    document.getElementById(key === null ? "tickets-heading" : "desk-heading")?.focus();
  }, [key]);

  const blocked = closed || busy || generation === null || !settled;

  async function decide(decision: "approved" | "rejected", reason?: string) {
    if (item === null || generation === null || inFlight.current) return;
    const target = item;
    const targetKey = ticketKey(target);
    inFlight.current = true;
    setBusy(true);
    const outcome = await sendDecision(
      { tenantId: target.tenantId, matchId, itemId: target.overlay.itemId },
      reason === undefined ? { decision, generation } : { decision, generation, reason },
    );
    inFlight.current = false;
    setBusy(false);
    const headline = target.rendered?.headline ?? "";
    if (outcome.ok) {
      focusNext.current = true;
      setDecidedHere(targetKey);
      setSent((before) => new Set([...before, targetKey]));
      setMessage(
        decision === "approved"
          ? `Approved "${headline}". It airs from the match clock.`
          : `Rejected "${headline}". It stays off air.`,
      );
    } else {
      setMessage(`"${headline}": ${outcome.message}`);
    }
  }

  function sendReject(text: string) {
    const reason = cleanReason(text);
    if (reason === null) {
      setReasonError("Give a reason of one line, without links.");
      return;
    }
    setReasonError(null);
    void decide("rejected", reason);
  }

  function move(by: number) {
    const next = queue[Math.min(queue.length - 1, Math.max(0, index + by))];
    if (next) {
      focusNext.current = ticketKey(next) !== key;
      setMessage("");
      setChosen(ticketKey(next));
    }
  }

  function approve() {
    if (!blocked && rejectingFor === null && item && !correctedSince(view, item)) {
      void decide("approved");
    }
  }

  function reject() {
    if (blocked || key === null) return;
    setReasonError(null);
    setRejectingFor(key);
  }

  // The keys act on the screen as it is now: the handler reads the latest actions from a ref.
  const keys = useRef<Keys>({ approve: () => {}, reject: () => {}, move: () => {} });
  useEffect(() => {
    keys.current = { approve, reject, move };
  });
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.repeat || event.isComposing || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      if (event.shiftKey || isTyping(event.target)) return;
      const action = ACTIONS[event.key];
      if (action === undefined) return;
      // The key is spent on the shortcut: R must not also type into the reason it opens.
      event.preventDefault();
      if (action === "next") keys.current.move(1);
      else if (action === "previous") keys.current.move(-1);
      else if (action === "approve") keys.current.approve();
      else keys.current.reject();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const verdict = approvalsVerdict({ phase, waiting: queue, decided: log.length });
  const now = view.clock ? instant(view.clock.clock) : null;

  return (
    <>
      <header className="page-header">
        <h1>Approvals</h1>
        {title && <p>{title}</p>}
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
      <div className="approvals__controls">{switcher}</div>
      <p className="approvals__message" aria-live="polite">
        {message}
      </p>
      <div className="approvals__floor" data-empty={item === null || undefined}>
        <Tickets
          items={queue}
          moments={view.moments}
          current={key}
          onChoose={(next) => {
            focusNext.current = next !== key;
            setMessage("");
            setChosen(next);
          }}
          onMove={move}
          closed={phase === "finished"}
        />
        {item && (
          <Desk
            key={key}
            item={item}
            view={view}
            tenant={tenants?.get(item.tenantId)}
            actions={{
              blocked,
              busy,
              rejecting: rejectingFor === key,
              reasonError,
              onApprove: approve,
              onReject: reject,
              onCancel: () => setRejectingFor(null),
              onSendReject: sendReject,
            }}
          />
        )}
      </div>
      <DecisionLog items={log} now={now} />
    </>
  );
}
