"use client";

import type { OperationsReport } from "@/contracts/operations";
import { parseOperations } from "@/domain/operations";
import { type Polled, POLL_MS, READ_TIMEOUT_MS, usePolled } from "@/lib/usePolled";

export { POLL_MS, READ_TIMEOUT_MS };

export type Lookup = Polled<OperationsReport>;

/** The matchday run as the API measured it, read on arrival and every few seconds after. */
export function useOperations(): Lookup {
  return usePolled("/api/operations", parseOperations);
}
