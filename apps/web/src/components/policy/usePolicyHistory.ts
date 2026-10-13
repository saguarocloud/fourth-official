"use client";

import { useEffect, useState } from "react";

import type { PolicyChange, PolicyHistory } from "@/contracts/policyHistory";
import { parseHistory } from "@/domain/policy";

export type Lookup =
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly history: PolicyHistory }
  | { readonly status: "unavailable" };

const LOADING: Lookup = { status: "loading" };

interface Settled {
  readonly key: string;
  readonly lookup: Lookup;
}

async function lookUp(tenantId: string, signal: AbortSignal): Promise<Lookup> {
  const response = await fetch(`/api/policies/${tenantId}`, { cache: "no-store", signal });
  if (!response.ok) return { status: "unavailable" };
  const history = parseHistory(await response.json());
  return history ? { status: "ready", history } : { status: "unavailable" };
}

/** A partner's policy history, read on arrival and again on reload (after a save, say). */
export function usePolicyHistory(tenantId: string): {
  readonly lookup: Lookup;
  readonly reload: () => void;
} {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled | null>(null);
  const key = `${attempt}:${tenantId}`;

  useEffect(() => {
    const controller = new AbortController();
    lookUp(tenantId, controller.signal)
      .catch((): Lookup => ({ status: "unavailable" }))
      .then((lookup) => {
        if (!controller.signal.aborted) setSettled({ key, lookup });
      });
    return () => controller.abort();
  }, [tenantId, key]);

  const lookup = settled?.key === key ? settled.lookup : LOADING;
  return { lookup, reload: () => setAttempt((n) => n + 1) };
}

export type Outcome<T> =
  | { readonly ok: true; readonly change: T }
  | { readonly ok: false; readonly status: number; readonly detail: string };

const NO_ANSWER = "The policy service did not answer. Nothing was changed.";

async function send<T>(path: string, body: unknown): Promise<Outcome<T>> {
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Requested-By": "fourth-official" },
      body: JSON.stringify(body),
    });
    const answer = (await response.json()) as { detail?: unknown };
    if (response.ok) return { ok: true, change: answer as T };
    const detail = typeof answer.detail === "string" ? answer.detail : NO_ANSWER;
    return { ok: false, status: response.status, detail };
  } catch {
    return { ok: false, status: 0, detail: NO_ANSWER };
  }
}

export interface EditBody {
  readonly policy?: Record<string, unknown>;
  readonly yaml?: string;
  readonly baseVersion: number;
  readonly reason: string;
}

export function saveEdit(tenantId: string, edit: EditBody): Promise<Outcome<PolicyChange>> {
  return send(`/api/policies/${tenantId}`, edit);
}

export function resetPolicies(
  reason: string,
): Promise<Outcome<{ readonly changes: readonly PolicyChange[] }>> {
  return send("/api/policies/reset", { reason });
}
