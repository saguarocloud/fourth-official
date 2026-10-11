"use client";

import { useEffect, useState } from "react";

/** A partner as the studio needs it for approvals: which items wait, and who decides on them. */
export interface TenantInfo {
  readonly tenantId: string;
  readonly approvalRequired: readonly string[];
  readonly dutyEditor: string;
}

function isTenant(value: unknown): value is TenantInfo {
  const t = value as Partial<TenantInfo> | null;
  return (
    typeof t?.tenantId === "string" &&
    typeof t.dutyEditor === "string" &&
    Array.isArray(t.approvalRequired) &&
    t.approvalRequired.every((k) => typeof k === "string")
  );
}

/** The partners, loaded once: null until they arrive, or if the match service is unavailable. */
export function useTenants(): ReadonlyMap<string, TenantInfo> | null {
  const [tenants, setTenants] = useState<ReadonlyMap<string, TenantInfo> | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/tenants", { cache: "no-store", signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("tenants"))))
      .then((body: { tenants?: unknown }) => {
        const listed = Array.isArray(body.tenants) ? body.tenants.filter(isTenant) : [];
        setTenants(new Map(listed.map((t) => [t.tenantId, t])));
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);
  return tenants;
}
