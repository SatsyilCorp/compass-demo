"use client";

/**
 * React view of the rehearsal acting persona. Components on the rehearsal
 * plane use this so form scope (columns, filters, row counts) follows the
 * acting persona, keeping the browser request coherent with the replay
 * adapters. Live-evidence components never use it.
 */
import { useSyncExternalStore } from "react";

import type { Role } from "@/lib/types";
import { ORG_UNIT_FOR_ROLE } from "@/lib/auth/identity-contract";
import {
  REHEARSAL_PERSONA_KEY,
  getRehearsalPersonaOverride,
} from "@/lib/mock/rehearsal-persona";

function subscribe(listener: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === REHEARSAL_PERSONA_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener("compass:rehearsal-persona", listener);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("compass:rehearsal-persona", listener);
  };
}

export function useRehearsalIdentity(
  authRole: Role | null,
  authOrgUnit: string | null,
): { role: Role | null; orgUnit: string | null } {
  const override = useSyncExternalStore(subscribe, getRehearsalPersonaOverride, () => null);
  if (override) return { role: override, orgUnit: ORG_UNIT_FOR_ROLE[override] };
  return { role: authRole, orgUnit: authOrgUnit };
}
