"use client";

import { Play } from "lucide-react";
import { useState, useSyncExternalStore } from "react";

import { KeyButton } from "@/components/ui/KeyButton";

import type { MatchdayAvailability } from "./types";

interface StartMatchdayProps {
  readonly running: boolean;
  /** The API's latest answer on whether a run may start; null until it has answered. */
  readonly availability: MatchdayAvailability | null;
  readonly onStarted: () => void;
}

interface Note {
  readonly tone: "amber" | "red";
  readonly text: string;
  /** Whether a matchday was running when the note was written: it lapses when that changes. */
  readonly running: boolean;
}

function everySecond(onTick: () => void): () => void {
  const timer = setInterval(onTick, 1000);
  return () => clearInterval(timer);
}

function never(): () => void {
  return () => undefined;
}

const currentSecond = () => Math.floor(Date.now() / 1000) * 1000;
const stopped = () => 0;

/** The current time to the second, ticking while `active`. */
function useNow(active: boolean): number {
  return useSyncExternalStore(
    active ? everySecond : never,
    active ? currentSecond : stopped,
    stopped,
  );
}

function countdown(milliseconds: number): string {
  const seconds = Math.ceil(milliseconds / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function utcTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

/** Starts the replay of the whole matchday. Runs are spaced by a cooldown and a daily
 * allowance; the key shows both before anyone presses it. */
export function StartMatchday({ running, availability, onStarted }: StartMatchdayProps) {
  const [busy, setBusy] = useState(false);
  // Accepted, and waiting for the next poll to show the run: the key stays busy until then.
  const [awaiting, setAwaiting] = useState(false);
  const [wasRunning, setWasRunning] = useState(running);
  if (running !== wasRunning) {
    setWasRunning(running);
    if (running) setAwaiting(false);
  }
  const [note, setNote] = useState<Note | null>(null);
  const cooling = !running && availability?.blockedBy === "cooldown" && !!availability.readyAt;
  const now = useNow(cooling);
  const remaining = cooling ? Date.parse(availability.readyAt!) - now : 0;
  const spent = !running && availability?.blockedBy === "daily_limit";

  async function start() {
    setBusy(true);
    setNote(null);
    try {
      const response = await fetch("/api/matchday", { method: "POST" });
      if (response.status === 202) {
        setAwaiting(true);
        onStarted();
        return;
      }
      const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
      const detail =
        typeof body.detail === "string" ? body.detail : "The matchday could not start.";
      setNote({ tone: response.status === 409 ? "amber" : "red", text: sentence(detail), running });
    } catch {
      setNote({
        tone: "red",
        text: "The match service is unavailable. Try again shortly.",
        running,
      });
    } finally {
      setBusy(false);
    }
  }

  // A run too short for any poll to see running ends in its cooldown: that answer settles it too.
  const starting = busy || (awaiting && !running && (availability?.ready ?? true));
  const label = starting
    ? "Starting…"
    : running
      ? "Matchday running"
      : remaining > 0
        ? `Ready in ${countdown(remaining)}`
        : "Start matchday";
  const shown: Pick<Note, "tone" | "text"> | null =
    note !== null && note.running === running
      ? note
      : spent && availability.reason
        ? {
            tone: "amber",
            text: `${sentence(availability.reason)}${
              availability.readyAt ? ` Ready again at ${utcTime(availability.readyAt)} UTC.` : ""
            }`,
          }
        : null;

  return (
    <div className="start-matchday">
      <KeyButton
        intent="primary"
        onClick={start}
        loading={starting}
        disabled={running || remaining > 0 || spent}
      >
        {!starting && (
          <Play aria-hidden="true" strokeWidth={1.75} className="start-matchday__icon" />
        )}
        {label}
      </KeyButton>
      {shown && (
        <p role="status" className="start-matchday__note" data-tone={shown.tone}>
          {shown.text}
        </p>
      )}
    </div>
  );
}

function sentence(text: string): string {
  const trimmed = text.trim();
  const capital = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return /[.!?]$/.test(capital) ? capital : `${capital}.`;
}
